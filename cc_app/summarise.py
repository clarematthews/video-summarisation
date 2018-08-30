import os
import time
import cv2
import featurespace as fs
import numpy as np
import threading
import contextlib
from rq import get_current_job

BUFFER = 20
MINSHOT = 2
THRESH = 0.5
FPS = 2
VIDLENGTH = 15
NFRAMES = FPS*VIDLENGTH
WAIT = 2


def framename(num):
    return 'img{:06d}.png'.format(num)


def nextframe(template, framenum):
    filename = template.format(framenum)
    trial = 1
    numtrials = 10.0
    trialwait = WAIT/numtrials
    while not os.path.isfile(filename) and trial < numtrials:
        trial += 1
        time.sleep(trialwait)

    if os.path.isfile(filename):
        return filename


def process(filename):
    rgb = cv2.imread(filename, 1)
    return fs.rgb_moments(rgb)


def select_keyframe(features):
    mu = features.mean(0)
    dists = np.apply_along_axis(lambda f: np.linalg.norm(f - mu), axis=1,
            arr=features)
    return np.argmin(dists)


def normhhist(rgbim):
    maxhue = 179
    hsv = cv2.cvtColor(rgbim, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    hist = np.histogram(h, bins=16, range=(0, maxhue))[0]
    norm = np.linalg.norm(hist)
    if norm == 0:
        return hist
    return hist/norm


def framediff(frame1, frame2):
    hist1 = normhhist(frame1)
    hist2 = normhhist(frame2)
    return sum(abs(hist1 - hist2))


def dynamicthresh(base, numkf, budget, time, totaltime, dim):
    expkf = budget*time/totaltime
    if expkf == budget:
        thresh =  (numkf >= budget)*dim
    else:
        thresh =  (base*(budget - numkf) + dim*(numkf - expkf))/(budget - expkf)
    return thresh


def mostsimilarframe(similarities):
    minidx = similarities.index(min(similarities))
    presim = float('inf')
    postsim = float('inf')
    if minidx > 0:
        presim = similarities[minidx - 1]
    if minidx < len(similarities) - 1:
        postsim = similarities[minidx + 1] 
    if presim < postsim:
        return minidx - 1
    else:
        return minidx


def run(path, fnames, budget):
    job = get_current_job()
    while not os.listdir(path):
        print('Waiting for stream...')
        time.sleep(5)
    
    print('Running algorithm')
    frames = []
    fstframe = os.listdir(path)
    fstframe = fstframe[0]
    fstframe = int(float(fstframe[3:9]))
    framenum = fstframe
    distcount = 0
    kfs = []
    adjkfsim = []
    nextfile = nextframe(fnames, framenum)
    sumdist = 0
    sumsq = 0
    while nextfile:
        print(framenum)
        frames.append({'file': framename(framenum), 'keyframe': False})
        job.meta['frames'] = frames
        job.save_meta()
        currfeatures = process(nextfile)
        simdim = len(currfeatures)
        if framenum == fstframe:
            shot = currfeatures
            eventframes = [nextfile,] 
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        dist = np.linalg.norm(currfeatures - prevfeatures)
        if framenum - fstframe < BUFFER:
            sumdist += dist
            sumsq += dist**2
            distcount += 1
            shot = np.append(shot, currfeatures, axis=0)
            eventframes.append(framenum)
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        mu = sumdist/distcount
        sig = np.sqrt(sumsq/distcount - mu**2)
        if dist < mu + 3*sig:
            sumdist += dist
            sumsq += dist**2
            distcount += 1
            shot = np.append(shot, currfeatures, axis=0)
            eventframes.append(framenum)
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        if shot.shape[0] < MINSHOT:
            shot = currfeatures
            eventframes = [framenum,]
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        idx = select_keyframe(shot)
        currkf = eventframes[idx]
        if len(kfs) == 0:
            kfs.append(currkf)
            adjkfsim.append(1)
            try:
                imfile = framename(currkf)
                idx = frames.index({'file': imfile, 'keyframe': False})
                frames[idx] = {'file': imfile, 'keyframe': True}
            except ValueError:
                pass
            print('Added first KF: {}'.format(currkf))
            prevshot = shot
            shot = currfeatures
            eventframes = [framenum,]
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        print('Keyframes-------: {}'.format(kfs))
        prevkf = kfs[-1]
        currim = cv2.imread(fnames.format(currkf), 1)
        previm = cv2.imread(fnames.format(prevkf), 1)
        diff = framediff(currim, previm)
        currkfs = len(kfs)
        if currkfs < budget:
            dynthresh = dynamicthresh(THRESH, currkfs, budget, framenum,
                    NFRAMES, simdim)
            if diff >= dynthresh: 
                kfs.append(currkf)
                adjkfsim.append(diff)
                try:
                    imfile = framename(currkf)
                    idx = frames.index({'file': imfile, 'keyframe': False})
                    frames[idx] = {'file': imfile, 'keyframe': True}
                except ValueError:
                    pass
                print('Added KF: {}'.format(currkf))
        else:
            minsim = min(adjkfsim)
            if minsim <= diff:
                kfs.append(currkf)
                adjkfsim.append(diff)
                try:
                    imfile = framename(currkf)
                    idx = frames.index({'file': imfile, 'keyframe': False})
                    frames[idx] = {'file': imfile, 'keyframe': True}
                except ValueError:
                    pass
                print('Added KF: {}'.format(currkf))

                # Find frame to remove
                replace = mostsimilarframe(adjkfsim)

                # Update keyframe and similarity records
                preadj = kfs[replace - 1]
                postadj = kfs[replace + 1]
                preim = cv2.imread(fnames.format(preadj), 1)
                postim = cv2.imread(fnames.format(postadj), 1)
                newdiff = framediff(preim, postim)
                adjkfsim[replace + 1] = newdiff
                adjkfsim.pop(replace)
                replace = kfs.pop(replace)
                try:
                    imfile = framename(replace)
                    idx = frames.index({'file': imfile, 'keyframe': True})
                    frames[idx] = {'file': imfile, 'keyframe': False}
                except ValueError:
                    pass

        shot = currfeatures
        eventframes = [framenum,]
        prevfeatures = currfeatures
        framenum += 1
        nextfile = nextframe(fnames, framenum)


    ## Include last shot
    if len(eventframes) >= MINSHOT:
        idx = select_keyframe(shot)
        currkf = eventframes[idx]
        if len(kfs) > 0:
            prevkf = kfs[-1]
            currim = cv2.imread(fnames.format(currkf), 1)
            previm = cv2.imread(fnames.format(prevkf), 1)
            diff = framediff(currim, previm)
            currkfs = len(kfs)
            if currkfs < budget:
                dynthresh = dynamicthresh(THRESH, currkfs, budget, NFRAMES,
                        NFRAMES, simdim)
                if diff >= dynthresh:
                    kfs.append(currkf)
                    try:
                        imfile = framename(currkf)
                        idx = frames.index({'file': imfile, 'keyframe': False})
                        frames[idx] = {'file': imfile, 'keyframe': True}
                    except ValueError:
                        pass
                    print('Added KF: {}'.format(currkf))
            else:
                minsim = min(adjkfsim)
                if minsim <= diff:
                    # Add new frame
                    kfs.append(currkf)
                    try:
                        imfile = framename(currkf)
                        idx = frames.index({'file': imfile, 'keyframe': False})
                        frames[idx] = {'file': imfile, 'keyframe': True}
                    except ValueError:
                        pass
                    print('Added KF: {}'.format(currkf))

                    # Find frame to remove
                    adjkfsim.append(diff)
                    replace = mostsimilarframe(adjkfsim)

                    # Remove existing keyframe
                    replace = kfs.pop(replace)
                    try:
                        imfile = framename(replace)
                        idx = frames.index({'file': imfile, 'keyframe': True})
                        frames[idx] = {'file': imfile, 'keyframe': False}
                    except ValueError:
                        pass

    return kfs

