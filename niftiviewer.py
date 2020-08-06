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

# todo: 
# need to test with rgb data
# add overlay cmap parameter

def SliceView(data3d, plot_axis, view_axis, slice_number, 
    transparent = False, **kwargs):
    """
    Parameters
    ----------
    data3d: numpy array
    plot_axis: matplotlib axis
    view_axis: int
    slice_number: int
    """
    # thought I'd tested this and it worked? not working with pineapple_vibe.nii
 #   plot_axis.imshow(np.rot90(data3d.take(indices=slice_number, axis=view_axis)), **kwargs)
    plot_data = np.array(data3d).take(indices=slice_number, axis=view_axis)
    if transparent:
        plot_data = np.ma.masked_where(plot_data == 0, plot_data)

    plot_axis.imshow(np.rot90(plot_data), **kwargs)
    plot_axis.axis('off')


# how to do overlays?
def QuickView(niftipath, plot_array = [1,1], volno = 0, view_axis = 2, mag = 1, 
    crop = 0, slices = None, outfile = None, cmap = 'gray', overlay = None, 
    **kwargs):

    if slices and plot_array[0]*plot_array[1] != len(slices):
        plot_array[0] = 1
        plot_array[1] = len(slices)

    img = nib.load(str(niftipath))
    if len(img.shape) > 3:
        data = img.dataobj[:,:,:,volno]
    else:
        data = img.dataobj

    # todo: check if dimensions are consistent
    if overlay:
        overlay_img = nib.load(str(overlay))
        if len(img.shape) > 3:
            overlay_data = overlay_img.dataobj[:,:,:,volno]
        else:
            overlay_data = overlay_img.dataobj

    zooms = np.delete(img.header.get_zooms()[0:3], view_axis)
    aspect = zooms[1] / zooms[0]

    i = 1
    nrows = plot_array[0]
    ncols = plot_array[1]
    dpi = 72
    stampsize = np.array(data.shape)*mag/dpi
    plt.figure(figsize=(stampsize[0]* ncols, stampsize[1]*nrows), dpi = dpi)

    nslices = nrows * ncols

    if not slices:
        step = int(data.shape[view_axis]*(100-crop)/(100*(nslices+1)))
        start = step + int(0.5*data.shape[view_axis]*crop/100)
        slices = range(start, data.shape[view_axis] + 1 - step, step)



    for i,z in enumerate(slices[:nslices]):
        axis = plt.subplot(nrows, ncols, i+1)
        SliceView(data, plot_axis = axis, slice_number = z,
                  view_axis = view_axis, aspect = aspect, cmap = cmap, **kwargs)
        if overlay:
            SliceView(overlay_data, plot_axis = axis, slice_number = z,
                      view_axis = view_axis, aspect = aspect, transparent = True,
                      **kwargs)

    plt.tight_layout()
    if outfile:
        plt.savefig(outfile, bbox_inches = 'tight')
    plt.show()

def Orthoview(niftipath, slices=[0,0,0], volno = 0, overlay = None, cmap = 'gray', **kwargs):

    img = nib.load(str(niftipath))
    if len(img.shape) > 3:
        data = img.dataobj[:,:,:,volno]
    else:
        data = img.dataobj

    if overlay:
        overlay_img = nib.load(str(overlay))
        if len(img.shape) > 3:
            overlay_data = overlay_img.dataobj[:,:,:,volno]
        else:
            overlay_data = overlay_img.dataobj

    slice_indices = slices + np.array(img.shape[:3]) // 2

    aspect = []
    for view in range(0,3):
        zooms = np.delete(img.header.get_zooms()[0:3], view)
        aspect.append(zooms[1] / zooms[0])

    fig, axes = plt.subplots(1, 3, figsize=(30, 10))

    for i, ax in enumerate(axes):
        SliceView(data, plot_axis= ax, slice_number=slice_indices[i],
                  view_axis=i, aspect=aspect[i], cmap = cmap, **kwargs)
        if overlay:
            SliceView(overlay_data, plot_axis= ax, slice_number=slice_indices[i],
                  view_axis=i, aspect=aspect[i], transparent = True, **kwargs)

    plt.show()

# honestly don't remember why I wanted this
# the indices are VOLUME indices
def ViewByIndices(niftipath, indices, ncols = None, sliceno = None,
                  cmap = 'gray', view_axis = 2, mag = 1, **kwargs):

    img = nib.load(str(niftipath))
    data = img.dataobj

    if not sliceno:
        sliceno = int(data.shape[view_axis]/2)

    if not ncols:
        ncols = len(indices)
    nrows = math.ceil(len(indices)/ncols)

    dpi = 72
    stampsize = np.array(data.shape)*mag/dpi
    plt.figure(figsize=(stampsize[0]* ncols, stampsize[1]*nrows), dpi = dpi)

    for i,v in enumerate(indices):
        ax = plt.subplot(nrows, ncols, i+1)
        SliceView(data[...,v], plot_axis=ax, slice_number=sliceno, cmap = cmap,
                  view_axis=view_axis, **kwargs)
    plt.show()

## EVERYTHING BELOW THIS NEEDS FIXING STILL

# loop through like a movie DOES NOT WORK RIGHT NOW
def Loop(niftipath, sliceno = None, view_axis = 2, outfile = None):

    img = nib.load(str(niftipath))
    data = img.dataobj

    if not sliceno:
        sliceno = int(data.shape[view_axis]/2)

    if outfile:
        tmpdir = tempfile.TemporaryDirectory()

    plt.figure()

    for v in range(0,data.shape[-1]):
        SliceView(data[..., v], plot_axis=plt.gca(), slice_number=sliceno,
                  view_axis=view_axis, cmap = 'gray')
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