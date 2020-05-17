# useful routines for visually inspecting nifti files in a jupyter notebook

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import nibabel as nib
import math
from time import sleep
from IPython.display import clear_output
import tempfile
import subprocess
import os

# todo: add aspect handling for non-square pixels (dti too)
# fix redundancies in quickview functions
# generalize view for data that isn't axial to start with
# change view to axis for quickviewdata

def QuickView(niftipath, plot_array = (1,1), cmap = 'gray', volno = 0, view = 'axial', mag = 1, crop = 0, 
    outfile = None):

    img = nib.load(str(niftipath))
    if len(img.shape) > 3:
        data = img.dataobj[:,:,:,volno]
    else:
        data = img.dataobj
    zooms = img.header.get_zooms()

    axis = 2
    if view.lower().startswith('c'):
        axis = 1
    elif view.lower().startswith('s'):
        axis = 0

    data = np.moveaxis(data, axis, 2 - len(data.shape)) # send slice axis to the back (-1 for greyscale, -2 for rgb)
    zooms = np.roll(zooms, 2 - axis)
    aspect = zooms[1]/zooms[0]

    i = 1
    nrows = plot_array[0]
    ncols = plot_array[1]
    dpi = 72
    stampsize = np.array(data.shape)*mag/dpi
    plt.figure(figsize=(stampsize[0]* ncols, stampsize[1]*nrows), dpi = dpi)

    nslices = nrows * ncols

    step = int(data.shape[axis]*(100-crop)/(100*(nslices+1)))
    start = step + int(0.5*data.shape[axis]*crop/100)
    slices_to_plot = range(start, data.shape[2] + 1 - step, step)


    for i,z in enumerate(slices_to_plot[:nslices]):
        plt.subplot(nrows, ncols, i+1)
        plt.axis('off')
        plt.imshow(np.rot90(data.take(indices = z, axis = 2)), cmap=cmap, aspect = aspect)

    plt.tight_layout()
    if outfile:
        plt.savefig(outfile, bbox_inches = 'tight')
    plt.show()



def QuickViewData(data, plot_array = (1,1), cmap = 'gray', volno = 0, view = 'axial', mag = 1, crop = 0, 
    outfile = None, aspect = 'auto'):

    data = image # hope it's a numpy array or image proxy

    axis = 2
    if view.lower().startswith('c'):
        axis = 1
    elif view.lower().startswith('s'):
        axis = 0

    data = np.moveaxis(data, axis, 2 - len(data.shape)) # send slice axis to the back (-1 for greyscale, -2 for rgb)


    i = 1
    nrows = plot_array[0]
    ncols = plot_array[1]
    dpi = 72
    stampsize = np.array(data.shape)*mag/dpi
    plt.figure(figsize=(stampsize[0]* ncols, stampsize[1]*nrows), dpi = dpi)

    nslices = nrows * ncols

    step = int(data.shape[axis]*(100-crop)/(100*(nslices+1)))
    start = step + int(0.5*data.shape[axis]*crop/100)
    slices_to_plot = range(start, data.shape[2] + 1 - step, step)


    for i,z in enumerate(slices_to_plot[:nslices]):
        plt.subplot(nrows, ncols, i+1)
        plt.axis('off')
        plt.imshow(np.rot90(data.take(indices = z, axis = 2)), cmap=cmap)

    if outfile:
        plt.savefig(outfile, bbox_inches = 'tight')
    plt.show()

def ViewByIndices(niifile, indices, ncols, cmap = 'gray', view = 'a', mag = 1, sliceno = None):

    print(niifile)
    img = nib.load(niifile)

    axis = 2
    if view.lower().startswith('c'):
        axis = 1
    elif view.lower().startswith('s'):
        axis = 0

    data = np.moveaxis(img.dataobj, axis, -1) # send slice axis to the back

    if not sliceno:
        sliceno = int(data.shape[-1]/2)
    nrows = math.ceil(len(indices)/ncols)

    dpi = 72
    stampsize = np.array(data.shape)*mag/dpi
    plt.figure(figsize=(stampsize[0]* ncols, stampsize[1]*nrows), dpi = dpi)


    for i,v in enumerate(indices):
        plt.subplot(nrows, ncols, i+1)
        plt.axis('off')
        plt.imshow(np.rot90(data[...,v,sliceno]), cmap=cmap)
    plt.show()

# loop through like a movie
def Loop(image, cmap = 'gray', sliceno = None, view = 'a', outfile = None):   

    if type(image) is str: #assume it's a nifti file
        img = nib.load(image)
        data = img.dataobj

    else:
        data = image # hope it's a numpy array or image proxy

    axis = 2
    if view.lower().startswith('c'):
        axis = 1
    elif view.lower().startswith('s'):
        axis = 0

    data = np.moveaxis(data, axis, -1) # send slice axis to the back

    if len(data.shape) > 3:
        if not sliceno:
            sliceno = int(data.shape[-1]/2)
        data = data[...,sliceno]


    if outfile:
        tmpdir = tempfile.TemporaryDirectory()

    plt.figure()

    for v in range(0,data.shape[-1]):
        plt.axis('off')
        plt.imshow(np.rot90(data[...,v]), cmap=cmap)
        if outfile:
            plt.savefig(os.path.join(tmpdir.name, 'temp_{:03d}.png'.format(v)), bbox_inches = 'tight')
        plt.show()
        sleep(0.1)
        clear_output(wait=True)

    if outfile:
        subprocess.call(['convert', os.path.join(tmpdir.name, '*.png'), outfile])



def dtiView(fa_file, v1_file, plot_array = (1,1), view = 'axial', mag = 1, crop = 0, outfile = None):
    v1 = nib.load(v1_file)
    fa = nib.load(fa_file)
    fa_v1 = np.clip(fa.get_data(), 0, 1)[..., None]*np.abs(v1.get_data())
    QuickViewData(fa_v1, plot_array = plot_array, view = view, mag = mag, crop = crop, cmap = None, outfile = outfile)

# loop through multiple volumes in parallel
# Should be able to replace loop with this
# can be slow, mag can be a problem?
def NewLoop(volumes, cmap = 'gray', sliceno = None, view = 'a', outfile = None, mag = 1):   

    # if we weren't sent a list, make it a list
    if type(volumes) is not list:
        volumes = [volumes]

    # prep data
    plotdata = list()
    for image in volumes:

        if type(image) is str: #assume it's a nifti file
            img = nib.load(image)
            data = img.dataobj

        else:
            data = image # hope it's a numpy array or image proxy

        axis = 2
        if view.lower().startswith('c'):
            axis = 1
        elif view.lower().startswith('s'):
            axis = 0

        data = np.moveaxis(data, axis, -1) # send slice axis to the back

        if len(data.shape) > 3:
            if not sliceno:
                sliceno = int(data.shape[-1]/2)
            data = data[...,sliceno]

        plotdata.append(data)

    nvols = plotdata[0].shape[-1] 

    if outfile:
        tmpdir = tempfile.TemporaryDirectory()

    dpi = 72
    stampsize = np.array(plotdata[0].shape)*mag/dpi
    plt.figure(figsize=(stampsize[0]* nvols, 1), dpi = dpi)

    for v in range(0, nvols):
        for i, d in enumerate(plotdata):
            plt.subplot(1, len(plotdata), i+1)
            plt.axis('off')
            plt.imshow(np.rot90(d[...,v]), cmap=cmap)
        plt.gcf().tight_layout()
        if outfile:
            plt.savefig(os.path.join(tmpdir.name, 'temp_{:03d}.png'.format(v)), bbox_inches = 'tight')
        plt.show()
        sleep(0.1)
        clear_output(wait=True)

    if outfile:
        subprocess.call(['convert', os.path.join(tmpdir.name, '*.png'), outfile])