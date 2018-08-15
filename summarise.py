import os
import time
import cv2
import featurespace as fs
import numpy as np
import threading
import contextlib

BUFFER = 20
MINSHOT = 5
THRESH = 0.6
WAIT = 3

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


def cleanup(files, template):
    for filenum in files:
        fname = template.format(filenum)
        with contextlib.suppress(FileNotFoundError):
            os.remove(fname)


def run(path, fnames):
    while not os.listdir(path):
        print('Waiting for stream...')
        time.sleep(5)
    
    framenum = 1
    distcount = 0
    kfs = []
    oldframes = []
    previdx = []
    nextfile = nextframe(fnames, framenum)
    sumdist = 0
    sumsq = 0
    while nextfile:
        currfeatures = process(nextfile)
        if framenum == 1:
            shot = currfeatures
            frameidx = [framenum] 
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        dist = np.linalg.norm(currfeatures - prevfeatures)
        if framenum < BUFFER:
            sumdist += dist
            sumsq += dist**2
            distcount += 1
            shot = np.append(shot, currfeatures, axis=0)
            frameidx.append(framenum)
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
            frameidx.append(framenum)
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        if shot.shape[0] < MINSHOT:
            shot = currfeatures
            oldframes = frameidx
            frameidx = [framenum]
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            oldframes = [f for f in oldframes if f not in kfs]
            cleaner = threading.Thread(target=cleanup, args=(oldframes, fnames))
            cleaner.start()
            continue

        idx = select_keyframe(shot)
        currkf = frameidx[idx]
        if len(kfs) == 0:
            kfs.append(currkf)
            print('Added first KF: {}'.format(currkf))
            prevshot = shot
            previdx = frameidx
            shot = currfeatures
            frameidx = [framenum]
            prevfeatures = currfeatures
            framenum += 1
            nextfile = nextframe(fnames, framenum)
            continue

        oldframes = previdx
        prevkf = kfs[-1]
        filename = fnames.format(currkf)
        currim = cv2.imread(filename, 1)
        filename = fnames.format(prevkf)
        previm = cv2.imread(filename, 1)
        diff = framediff(currim, previm)
        if diff < THRESH:
            print('Removing KF: {}'.format(kfs[-1]))
            kfs.pop()
            previdx.extend(frameidx)
            frameidx = previdx
            shot = np.append(prevshot, shot, axis=0)
            idx = select_keyframe(shot)
            currkf = frameidx[idx]
            oldframes = []

        kfs.append(currkf)
        print('Added KF: {}'.format(currkf))
        prevshot = shot
        previdx = frameidx
        shot = currfeatures
        frameidx = [framenum]
        prevfeatures = currfeatures
        framenum += 1
        nextfile = nextframe(fnames, framenum)

        oldframes = [f for f in oldframes if f not in kfs]
        cleaner = threading.Thread(target=cleanup, args=(oldframes, fnames))
        cleaner.start()

    ## Include last shot
    idx = select_keyframe(shot) 
    currkf = frameidx[idx]
    oldframes = previdx
    oldframes.extend(frameidx)
    if len(kfs) > 0:
        prevkf = kfs[-1]
        filename = fnames.format(currkf)
        currim = cv2.imread(filename, 1)
        filename = fnames.format(prevkf)
        previm = cv2.imread(filename, 1)
        diff = framediff(currim, previm)
        if diff < THRESH:
            kfs.pop()
            previdx.extend(frameidx)
            frameidx = previdx
            shot = np.append(prevshot, shot, axis=0)
            idx = select_keyframe(shot)
            currkf = frameidx[idx]
    kfs.append(currkf)
    oldframes = [f for f in oldframes if f not in kfs]
    cleaner = threading.Thread(target=cleanup, args=(oldframes, fnames))
    cleaner.start()

    return kfs

