import os
import time
import cv2
import featurespace as fs
import numpy as np
import threading
import contextlib
from rq import get_current_job

BUFFER = 20
MINSHOT = 5
THRESH = 0.6
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



def run(path, fnames):
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
    prevframes = []
    nextfile = nextframe(fnames, framenum)
    sumdist = 0
    sumsq = 0
    while nextfile:
        print(framenum)
        frames.append({'file': framename(framenum), 'keyframe': False})
        job.meta['frames'] = frames
        job.save_meta()
        currfeatures = process(nextfile)
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
            try:
                imfile = framename(currkf)
                idx = frames.index({'file': imfile, 'keyframe': False})
                frames[idx] = {'file': imfile, 'keyframe': True}
            except ValueError:
                pass
            print('Added first KF: {}'.format(currkf))
            prevshot = shot
            prevframes = eventframes
            shot = currfeatures
            eventframes = [framenum,]
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        prevkf = kfs[-1]
        currim = cv2.imread(fnames.format(currkf), 1)
        previm = cv2.imread(fnames.format(prevkf), 1)
        diff = framediff(currim, previm)
        if diff < THRESH:
            print('Removing KF: {}'.format(kfs[-1]))
            kfs.pop()
            try:
                imfile = framename(prevkf)
                idx = frames.index({'file': imfile, 'keyframe': True})
                frames[idx] = {'file': imfile, 'keyframe': False}
            except ValueError:
                pass
            prevframes.extend(eventframes)
            eventframes = prevframes
            shot = np.append(prevshot, shot, axis=0)
            idx = select_keyframe(shot)
            currkf = eventframes[idx]

        kfs.append(currkf)
        try:
            imfile = framename(currkf)
            idx = frames.index({'file': imfile, 'keyframe': False})
            frames[idx] = {'file': imfile, 'keyframe': True}
        except ValueError:
            pass
        print('Added KF: {}'.format(currkf))
        prevshot = shot
        prevframes = eventframes
        shot = currfeatures
        eventframes = [framenum,]
        prevfeatures = currfeatures
        framenum += 1
        nextfile = nextframe(fnames, framenum)


    ## Include last shot
    idx = select_keyframe(shot) 
    currkf = eventframes[idx]
    if len(kfs) > 0:
        prevkf = kfs[-1]
        currim = cv2.imread(fnames.format(currkf), 1)
        previm = cv2.imread(fnames.format(prevkf), 1)
        diff = framediff(currim, previm)
        if diff < THRESH:
            kfs.pop()
            try:
                imfile = framename(prevkf)
                idx = frames.index({'file': imfile, 'keyframe': True})
                frames[idx] = {'file': imfile, 'keyframe': False}
            except ValueError:
                pass
            prevframes.extend(eventframes)
            eventframes = prevframes
            shot = np.append(prevshot, shot, axis=0)
            idx = select_keyframe(shot)
            currkf = eventframes[idx]
    kfs.append(currkf)
    try:
        imfile = framename(currkf)
        idx = frames.index({'file': imfile, 'keyframe': False})
        frames[idx] = {'file': imfile, 'keyframe': True}
    except ValueError:
        pass

    return kfs

