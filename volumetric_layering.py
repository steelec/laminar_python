# prior to this:
# 1.create a jar file with all the classes:
# jar cvf intensity.jar de/mpg/cbs/python/IntensityBackgroundEstimator.class de/mpg/cbs/utilities/Numerics.class de/mpg/cbs/libraries/ImageStatistics.class
# 2.compile with jcc:
# python -m jcc --jar intensity.jar --python intensity --build --classpath /home/pilou/Code/cbs/bazin --install --install-dir /home/pilou/Code/cbs/bazin/pylibs/
# 3.export library path to python:
# export PYTHONPATH=$PYTHONPATH:/home/pilou/Code/cbs/bazin/pylibs

import argparse
import numpy as np
import nibabel as nb
import cbstoolsjcc
import os
from io_volume import load_volume, save_volume
from io_mesh import load_mesh_geometry, save_mesh_geometry

def create_levelsets(tissue_prob_img, save_data=True, base_name=None):

    # load the data as well as filenames and headers for saving later
    prob_img = load_volume(tissue_prob_img)
    prob_data = prob_img.get_data()
    hdr = prob_img.get_header()
    aff = prob_img.get_affine()

    try:
        cbstoolsjcc.initVM(initialheap='6000m', maxheap='6000m')
    except ValueError:
        pass

    prob2level = cbstoolsjcc.SurfaceProbabilityToLevelset()

    prob2level.setProbabilityImage(cbstoolsjcc.JArray('float')((prob_data.flatten('F')).astype(float)))
    prob2level.setDimensions(prob_data.shape)
    zooms = [x.item() for x in hdr.get_zooms()]
    prob2level.setResolutions(zooms[0], zooms[1], zooms[2])
    prob2level.execute()

    levelset_data = np.reshape(np.array(prob2level.getLevelSetImage(),
                               dtype=np.float32), prob_data.shape,'F')

    levelset_img = nb.Nifti1Image(levelset_data, aff, hdr)

    if save_data:
        if not base_name:
            if not isinstance(tissue_prob_img, basestring):
                base_name = os.getcwd()
                print "saving to %s"%base_name
            else:
                dir_name = os.path.dirname(tissue_prob_img)
                base_name = os.path.basename(tissue_prob_img)
                base_name = os.path.join(dir_name, base_name[:base_name.find('.')])
        save_volume(base_name+'_levelset.nii.gz', levelset_img)

    return levelset_img

def layering(gwb_levelset, cgb_levelset, lut_dir, n_layers=10,
             save_data=True, base_name=None):

    # load the data as well as filenames and headers for saving later
    gwb_img = load_volume(gwb_levelset)
    gwb_data = gwb_img.get_data()
    hdr = gwb_img.get_header()
    aff = gwb_img.get_affine()

    cgb_data = load_volume(cgb_levelset).get_data()

    try:
        cbstoolsjcc.initVM(initialheap='6000m', maxheap='6000m')
    except ValueError:
        pass

    lamination=cbstoolsjcc.LaminarVolumetricLayering()
    lamination.setDimensions(gwb_data.shape[0],gwb_data.shape[1],gwb_data.shape[2])
    zooms = [x.item() for x in hdr.get_zooms()]
    lamination.setResolutions(zooms[0], zooms[1], zooms[2])

    lamination.setInnerDistanceImage(cbstoolsjcc.JArray('float')((gwb_data.flatten('F')).astype(float)))
    lamination.setOuterDistanceImage(cbstoolsjcc.JArray('float')((cgb_data.flatten('F')).astype(float)))
    lamination.setNumberOfLayers(n_layers)
    lamination.setTopologyLUTdirectory(lut_dir);
    lamination.execute()

    depth_data=np.reshape(np.array(lamination.getContinuousDepthMeasurement(),dtype=np.float32),gwb_data.shape,'F')
    layer_data=np.reshape(np.array(lamination.getDiscreteSampledLayers(),dtype=np.uint32),gwb_data.shape,'F')

    boundary_len = lamination.getLayerBoundarySurfacesLength()
    boundary_data=np.reshape(np.array(lamination.getLayerBoundarySurfaces(),dtype=np.float32),
                            (gwb_data.shape[0], gwb_data.shape[1], gwb_data.shape[2],
                             boundary_len),'F')

    depth_img = nb.Nifti1Image(depth_data, aff, hdr)
    layer_img = nb.Nifti1Image(layer_data, aff, hdr)
    boundary_img = nb.Nifti1Image(boundary_data, aff, hdr)

    if save_data:
        if not base_name:
            if not isinstance(gwb_levelset, basestring):
                base_name = os.getcwd()
                print "saving to %s"%base_name
            else:
                dir_name = os.path.dirname(gwb_levelset)
                base_name = os.path.basename(gwb_levelset)
                base_name = os.path.join(dir_name, base_name[:base_name.find('.')])

        save_volume(base_name + '_depth.nii.gz', depth_img)
        save_volume(base_name + '_layers.nii.gz', layer_img)
        save_volume(base_name + '_boundaries.nii.gz', boundary_img)

    return depth_img, layer_img, boundary_img


def profile_sampling(boundary_img, intensity_img, save_data=True, base_name=None):

    # load the data as well as filenames and headers for saving later
    boundary_img = load_volume(boundary_img)
    boundary_data = boundary_img.get_data()
    hdr = boundary_img.get_header()
    aff = boundary_img.get_affine()

    intensity_data = load_volume(intensity_img).get_data()

    try:
        cbstoolsjcc.initVM(initialheap='6000m', maxheap='6000m')
    except ValueError:
        pass

    sampler = cbstoolsjcc.LaminarProfileSampling()
    sampler.setIntensityImage(cbstoolsjcc.JArray('float')((intensity_data.flatten('F')).astype(float)))
    sampler.setProfileSurfaceImage(cbstoolsjcc.JArray('float')((boundary_data.flatten('F')).astype(float)))
    zooms = [x.item() for x in hdr.get_zooms()]
    sampler.setResolutions(zooms[0], zooms[1], zooms[2])
    sampler.setDimensions(boundary_data.shape)
    sampler.execute()

    profile_data = np.reshape(np.array(sampler.getProfileMappedIntensityImage(),
                              dtype=np.float32), boundary_data.shape,'F')

    profile_img = nb.Nifti1Image(profile_data, aff, hdr)

    if save_data:
        if not base_name:
            if not isinstance(intensity_img, basestring):
                base_name = os.getcwd()
                print "saving to %s"%base_name
            else:
                dir_name = os.path.dirname(intensity_img)
                base_name = os.path.basename(intensity_img)
                base_name = os.path.join(dir_name, base_name[:base_name.find('.')])
        save_volume(base_name+'_profiles.nii.gz', profile_img)

    return profile_img


def profile_meshing(profile_file, surf_mesh, save_data=True, base_name=None):

    profile_img = load_volume(profile_file)
    profile_data = profile_img.get_data()
    profile_len = profile_data.shape[3]
    hdr = profile_img.get_header()
    aff = profile_img.get_affine()

    in_coords = load_mesh_geometry(surf_mesh)['coords']
    in_faces = load_mesh_geometry(surf_mesh)['faces']

    try:
        cbstoolsjcc.initVM(initialheap='6000m', maxheap='6000m')
    except ValueError:
        pass

    mesher = cbstoolsjcc.LaminarProfileMeshing()

    mesher.setDimensions(profile_data.shape)
    zooms = [x.item() for x in hdr.get_zooms()]
    mesher.setResolutions(zooms[0], zooms[1], zooms[2])

    mesher.setProfileSurfaceImage(cbstoolsjcc.JArray('float')((profile_data.flatten('F')).astype(float)))
    mesher.setSurfacePoints(cbstoolsjcc.JArray('float')(in_coords.flatten().astype(float)))
    mesher.setSurfaceTriangles(cbstoolsjcc.JArray('int')(in_faces.flatten().astype(int)))

    mesher.execute()

    out_coords = np.zeros((in_coords.shape[0], in_coords.shape[1], profile_len))
    out_faces = np.zeros((in_faces.shape[0], in_faces.shape[1], profile_len))

    mesh_list = []
    for i in range(profile_len):
        current_mesh = {}
        current_mesh['coords'] = np.reshape(np.array(mesher.getSampledSurfacePoints(i),
                                            dtype=np.float32),in_coords.shape)
        current_mesh['faces'] =  np.reshape(np.array(mesher.getSampledSurfaceTriangles(i),
                                            dtype=np.float32),in_faces.shape)
        mesh_list.append(current_mesh)

    if save_data:
        if not base_name:
            if not isinstance(profile_file, basestring):
                base_name = os.getcwd()
                print "saving to %s"%base_name
            else:
                dir_name = os.path.dirname(intensity_img)
                base_name = os.path.basename(intensity_img)
                base_name = os.path.join(dir_name, base_name[:base_name.find('.')])

        for i in range(len(mesh_list)):
            save_mesh_geometry(base_name+'_%s.vtk'%str(i), mesh_list[i])


    return mesh_list
