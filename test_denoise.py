import torch
import torch.nn as nn
import common
from common import gaussian, normilize, nhwc_to_nchw, to_np
import numpy as np
from datasets import DatasetFromFolder
from torch.utils.data import DataLoader
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# import pybm3d
import scipy.misc
from convsparse_net import LISTAConvDict
from datasets import  DatasetFromNPZ
import arguments

USE_CUDA = torch.cuda.is_available()

def plot_res(img, img_n, res, name, log_path, other_res=None):
    """Plot clean/noisy/orig images
    """

    img = np.squeeze(img)
    img_n = np.squeeze(img_n)
    res = np.squeeze(res)

    def im_path(typ):
        return  os.path.join(log_path, '{}_{}.png'.format(typ, name))

    scipy.misc.toimage(img * 255, cmin=0.0, cmax=255).save(im_path('orig'))
    scipy.misc.toimage(img_n * 255, cmin=0.0, cmax=255).save(im_path('noisy'))
    scipy.misc.toimage(res * 255, cmin=0.0, cmax=255).save(im_path('ours'))

    if other_res is not None:
        sub_typ = 221
        scipy.misc.toimage(other_res * 255, cmin=0.0,
                           cmax=255).save(im_path('other'))
    else:
        sub_typ = 131

    plt.subplot(sub_typ)
    plt.imshow(img, cmap='gray')
    plt.title('original')
    plt.gca().axis('off')

    plt.subplot(sub_typ + 1)
    plt.imshow(img_n, cmap='gray')
    plt.title('noise {:.2f} db'.format(common.psnr(img, img_n)))
    plt.gca().axis('off')

    plt.subplot(sub_typ + 2)
    plt.imshow(res, cmap='gray')
    plt.title('ours psnr {:.2f} db'.format(common.psnr(img, res)))
    plt.gca().axis('off')

    if other_res is not None:
        plt.subplot(sub_typ + 3)
        plt.imshow(res, cmap='gray')
        plt.title('other psnr {:.2f} db'.format(common.psnr(img, other_res)))
        plt.gca().axis('off')
    plt.savefig(os.path.join(log_path, 'res_{}'.format(name)))
    plt.clf()

def restore_model(model_args, saved_model_path):
    model = LISTAConvDict(
        num_input_channels=model_args['num_input_channels'],
        num_output_channels=model_args['num_output_channels'],
        kc=model_args['kc'],
        ks=model_args['ks'],
        ista_iters=model_args['ista_iters'],
        iter_weight_share=model_args['iter_weight_share'],
        share_decoder=model_args['share_decoder']
    )
    common.load_eval(saved_model_path, model)
    return model

def create_famous_dataset(test_path, noise, pad):

    def pre_process_fn(_x):
        return normilize(_x, 255)

    def input_process_fn(_x):
        return gaussian(_x, is_training=True, mean=0, stddev=normilize(noise, 255))

    return DatasetFromFolder(
                test_path,
                pre_transform=pre_process_fn,
                use_cuda=USE_CUDA,
                inputs_transform=input_process_fn
            )

def create_test_dataset(test_path, noise, pad):

    def pre_process_fn(_x):
        return normilize(_x, 255)

    def input_process_fn(_x):
        return gaussian(_x, is_training=True, mean=0, stddev=normilize(noise, 255))

    file_of_filenames =\
            os.path.join(common.project_dir(), 'pascal2010_test_imgs.txt')

    return DatasetFromFolder(
                test_path,
                file_of_filenames=file_of_filenames,
                pre_transform=pre_process_fn,
                use_cuda=USE_CUDA,
                inputs_transform=input_process_fn
            )

def avarge_psnr_testset(model, test_loader, border, noise):

    padder =  nn.ReflectionPad2d(border)

    def _to_np(_img):
        return to_np(_img)[0, 0, border:-border, border:-border]

    # def _bm3d(_img_n):
    #     return -1
    #     res = pybm3d.bm3d.bm3d(to_np(_img_n)[0, 0, ...], noise)
    #     #res[np.where(np.isnan(res))] = 0
    #     return res[border:-border, border:-border]

    ours_psnr = 0
    # bm3d_psnr = 0
    avg_over = len(test_loader)

    print('running avg psnr avg_over image count')
    img_count = 0
    for img, img_n in test_loader:

        img = padder(img)
        img_n = padder(img_n)

        output, _ = model(img_n)

        np_img = _to_np(img)
        np_output = np.clip(_to_np(output), 0, 1)
        # bm3d_img = np.clip(_bm3d(img_n), 0, 1)

        # bm3d_psnr += common.psnr(np_img, bm3d_img)
        ours_psnr += common.psnr(np_img, np_output)

        img_count += 1
        if img_count == avg_over:
            break
    # bm3d_psnr = bm3d_psnr / img_count
    ours_psnr = ours_psnr / img_count
    print(f'testset avargs of {img_count} psnr ours - {ours_psnr}')  # , bm3d - {bm3d_psnr}')
    return ours_psnr  # , bm3d_psnr

def famous_images_teset(model, test_loader, image_names, border, noise):
    """Run and save tests on specific images.
    """
    padder =  nn.ReflectionPad2d(border)

    def _to_np(x):
        return to_np(x)[0, 0, border:-border, border:-border]

    # def _bm3d(x):
    #     res = pybm3d.bm3d.bm3d(to_np(x)[0, 0, ...], noise)
    #     res[np.where(np.isnan(res))] = 0
    #     return res[border:-border, border:-border]


    psnrs = []
    res_array = []
    idx = 0
    for test_data, test_name in zip(test_loader, image_names):

        img, img_n = test_data
        img = padder(img)
        img_n = padder(img_n)

        output, _ = model(img_n)

        np_img = _to_np(img)
        np_output = np.clip(_to_np(output), 0, 1)
        np_img_n = _to_np(img_n)

        # bm3d_img = _bm3d(img_n)

        # bm3d_psnr = common.psnr(np_img, bm3d_img)
        ours_psnr = common.psnr(np_img, np_output, False)
        # psnrs.append({'ours': ours_psnr, 'bm3d': bm3d_psnr})
        res_array.append((np_img, np_img_n, np_output, bm3d_img))

        # print('Test Image {} psnr ours {} bm3d {}'.format(test_name, ours_psnr,
        #                                            bm3d_psnr))
        print('Test Image {} psnr ours {}'.format(test_name, ours_psnr))
        idx += 1

    # print('Avg famous psnr ours: {} other: {}'.format(np.mean([p['ours'] for p in psnrs]),
    #                                            np.mean([p['bm3d'] for p in psnrs])))
    print('Avg famous psnr ours: {}'.format(np.mean([p['ours'] for p in psnrs])))
    return psnrs, res_array

def test(args, saved_model_path, noise, famous_path, testset_path=None):
    """Run predictable test
    """
    torch.manual_seed(7)

    model = restore_model(args, saved_model_path)
    if USE_CUDA:
        model = model.cuda()

    norm_noise = common.normilize(noise, 255)
    padding = 20

    if testset_path is not None and os.path.isdir(testset_path):
        testset = create_test_dataset(testset_path, noise, padding)
        test_loader = DataLoader(testset)
        # ours_psnr, bm3d_psnr = avarge_psnr_testset(model, test_loader,
        #                                            padding, norm_noise)
        ours_psnr = avarge_psnr_testset(model, test_loader,
                                                   padding, norm_noise)
    else:
        print('testset path was not provided or does not exsist on machine'
              +' skipping to famouse images testset')
        ours_psnr = 0  # bm3d_psnr = 0

    testset = create_famous_dataset(famous_path, noise, padding)
    file_names = testset.image_filenames
    famous_loader = DataLoader(testset)

    fam_psnrs, fam_res_array =\
            famous_images_teset(
                model,
                famous_loader,
                file_names,
                padding,
                norm_noise)

    return fam_psnrs, fam_res_array, file_names, ours_psnr  # , bm3d_psnr


def _test(args_file):
    _args = arguments.load_args(args_file)
    test_args = _args['test_args']
    model_args = _args['model_args']

    model_path = test_args['load_path']
    famous_ims = test_args["testset_famous_path"]
    voc_ims = test_args["testset_pascal_path"]
    noise = test_args['noise']

    log_dir = os.path.dirname(model_path)
    # psnr, res, file_names, ours_psnr, bm3d_psnr =\
    #         test(model_args, model_path, noise, famous_ims, voc_ims)
    psnr, res, file_names, ours_psnr =\
            test(model_args, model_path, noise, famous_ims, voc_ims)
    for f_name, ims in zip(file_names, res):
        plot_res(ims[0], ims[1], ims[2], f_name, log_dir, ims[3])


def main():
    """Run test on trained model.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--args_file', default='saved_models/acsc4/params.json')
    args_file = parser.parse_args().args_file

    _test(args_file)


if __name__ == '__main__':
    main()

