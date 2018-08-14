import numpy as np

def rgb_moments(image):
    channels = 3
    blocks = 3
    imsize = image.shape 
    image = image[np.mod(imsize[0], blocks):imsize[0], np.mod(imsize[1], blocks):imsize[1], :]
    nrows = imsize[0]//blocks
    ncols = imsize[1]//blocks
    rgbblocks = image.reshape(blocks, nrows, blocks, ncols, channels)
    mu = rgbblocks.mean(3).mean(1).reshape(1, blocks*blocks*channels)
    sig = rgbblocks.std(3).std(1).reshape(1, blocks*blocks*channels)
    return np.concatenate((mu, sig), axis=1)
