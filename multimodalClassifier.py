import torch
import numpy
import random
from torch import nn
import re
import pickle
from collections import OrderedDict
import os
os.environ['http_proxy'] = ''   # This line for preventing Visdom from not showing anything.

from basicClassifier import basicClassifier
from audioClassifier import AudioClassifierNet
from skeletonClassifier import SkeletonClassifierNet
from videoFeatureExtractor import VideoFeatureExtractorNet
from videoClassifier import VideoClassifierNet

class MultimodalNet(nn.Module):
    def __init__(self, num_of_classes, dlength=183, pretrainedPaths=None):
        """

        :param num_of_classes:
        :param dlength: length of pose-descriptor
        """
        super().__init__()
        self.num_of_classes = num_of_classes
        self.dlength = dlength
        self.nframes = 5
        # 用于在forward方法中把输入弄上GPU
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

        if pretrainedPaths is None:
            print(f'Please set pretrainedPaths.')
            return

        # 建立前面的小网络们
        self.video_network = VideoClassifierNet(num_of_classes, pretrainedPaths['videoFeat'])
        self.mocap_network = SkeletonClassifierNet(num_of_classes, dlength)
        self.audio_network = AudioClassifierNet(num_of_classes)

        # print('self.left_network.children() is :')
        # for idx, m in enumerate(self.left_network.children()):
        #     print(idx, '->', m)

        # 然后加载预训练的模型
        # video
        extractor_dict = torch.load(pretrainedPaths['video'])
        self.video_network.load_state_dict(extractor_dict)
        self.video_network = nn.Sequential(OrderedDict(list(self.video_network.named_children())))
        # mocap
        extractor_dict = torch.load(pretrainedPaths['mocap'])
        self.mocap_network.load_state_dict(extractor_dict)
        self.mocap_network = nn.Sequential(OrderedDict(list(self.mocap_network.named_children())))
        # audio
        extractor_dict = torch.load(pretrainedPaths['audio'])
        self.audio_network.load_state_dict(extractor_dict)
        self.audio_network = nn.Sequential(OrderedDict(list(self.audio_network.named_children())))

        # 加上新的融合层(先在 forward 中完成concat，即torch.cat)
        concat_multi_in_size = 84 + 350 + 350   # video fc3, mocap fc3 , audio fc2
        self.concat_multi_fc1 = nn.Sequential(
            nn.Dropout(p=.0),
            nn.Linear(concat_multi_in_size, 120),
            nn.Tanh(),
            nn.BatchNorm1d(120),
        )

        self.concat_multi_fc2 = nn.Sequential(
            nn.Dropout(p=.0),
            nn.Linear(120, 60),
            nn.Tanh(),
            nn.BatchNorm1d(60),
        )

        self.output_block = nn.Sequential(
            nn.Dropout(p = .0),
            nn.Linear(60, self.num_of_classes),
            nn.Softmax(dim=1),
            nn.BatchNorm1d(self.num_of_classes)
        )





    def forward(self, x):
        # print(f'Type of multimodal input is : {type(x)}')
        # print(f'In multimodal, x keys are: {x.keys()}')
        # print(f'x is : {len(x["mocap"])}')
        # x = x.squeeze()
        # print(f'In multimodal, after squeeze(), x size is: {x.shape}')

        # print(f"Before going to GPU, type is: {x['video'].dtype}")
        # print(f"Before going to GPU, type is: {x['mocap'].dtype}")
        # print(f"Before going to GPU, type is: {x['mocap'].dtype}")
        # x = x.view(x.size(0), -1)


        # # v3.0 将四个视频模态 r_color, r_depth, l_color, l_depth 合成到 video 模态
        # # tmp_video = x['r_color'].unsqueeze(0)
        # cat_list = []
        # for video_mdlt in ['r_color', 'r_depth', 'l_color', 'l_depth']:
        #     # tmp_video.append(x[video_mdlt].data)
        #     cat_list.append(x[video_mdlt].unsqueeze(1))
        # tmp_video = torch.cat(cat_list, 1)

        # v3.0.1 将 color_video 和 depth_video 合并得到 video 模态
        # print(f"type(x['color_video'] = {type(x['color_video'])}, shape={x['color_video'].shape}")
        # print(f"type(x['depth_video'] = {type(x['depth_video'])}, shape={x['depth_video'].shape}")
        x['color_video'] = x['color_video'].permute(1, 0, 2, 3, 4, 5)
        x['depth_video'] = x['depth_video'].permute(1, 0, 2, 3, 4, 5)

        tmp_video = torch.cat([x['color_video'][0].unsqueeze(0), x['depth_video'][0].unsqueeze(0), x['color_video'][1].unsqueeze(0), x['depth_video'][1].unsqueeze(0)], 0)

        tmp_video = tmp_video.permute(1, 0, 2, 3, 4, 5)
        # x['color_video'] = x['color_video'].permute(1, 0, 2, 3, 4, 5)
        # x['depth_video'] = x['depth_video'].permute(1, 0, 2, 3, 4, 5)

        # print(f'type(tmp_video) = {type(tmp_video)}')
        # print(f'tmp_video.shape = {tmp_video.shape}')
        # print(f'type(tmp_video[0]) = {type(tmp_video[0])}')
        # print(f'x[""].shape = {x["r_color"].unsqueeze(0).shape}')

        # tmp_video = numpy.array(tmp_video).astype(numpy.float32)
        # tmp_video = torch.tensor(tmp_video)

        # x_video = x['video'].to(self.device)
        x_video = tmp_video.to(self.device)
        x_mocap = x['mocap'].to(self.device)
        x_audio = x['audio'].to(self.device)

        # print(f'In multimodal, x_video size is: {x_video.shape}, type is: {x_video.dtype}')
        # print(f'In multimodal, x_mocap size is: {x_mocap.shape}, type is: {x_mocap.dtype}')
        # print(f'In multimodal, x_audio size is: {x_audio.shape}, type is: {x_audio.dtype}')

        x_video = self.videoForward(x_video)
        x_mocap = self.mocapForward(x_mocap)
        x_audio = self.audioForward(x_audio)

        x = torch.cat([x_video, x_mocap, x_audio], 1)

        x = self.concat_multi_fc1(x)
        x = self.concat_multi_fc2(x)

        x = self.output_block(x)

        return x

    def videoForward(self, x):
        x = x.permute(1, 0, 2, 3, 4, 5)
        # print(f'In video classifier, x size is: {x.shape}')
        x0 = x[:2].permute(1, 0, 2, 3, 4, 5)
        x1 = x[2:].permute(1, 0, 2, 3, 4, 5)

        # print(f'In video classifier, after permutation, x0 size is: {x0.shape}')

        # x0 = self.right_network.forward(x0)
        # x1 = self.left_network.forward(x1)
        x0 = self.videoFeatForward(self.video_network.right_network, x0)
        x1 = self.videoFeatForward(self.video_network.left_network, x1)

        x0 = x0.view(x0.size(0), -1)
        x1 = x1.view(x1.size(0), -1)

        x = torch.cat([x0, x1], 1)

        x = self.video_network.fc3(x)

        return x

    def videoFeatForward(self, network, x):
        '''
        :param x: x[0] 为color的输入，x[1] 为 depth 的输入
        :return:
        '''
        x = x.permute(1, 0, 2, 3, 4, 5)

        x0 = x[0].permute(0, 2, 1, 3, 4) # 维度换位, 换完是
        x1 = x[1].permute(0, 2, 1, 3, 4)
        x0 = network.block1_color(x0)
        x1 = network.block1_depth(x1)
        x0 = x0.squeeze(2)
        x1 = x1.squeeze(2)
        x0 = network.block2_color(x0)
        x1 = network.block2_depth(x1)
        x0 = x0.view(x0.size(0), -1)
        x1 = x1.view(x1.size(0), -1)
        x = torch.cat([x0, x1], 1)
        x = network.block_fusion(x)

        return x

    def mocapForward(self, x):

        if x.shape[0] == 1:
            # 若 batch size == 1, 则把第一维再补回来
            x = x.squeeze()
            x = x.unsqueeze(0)
        else:
            x = x.squeeze()

        # print(f'In Skeleton, after squeeze(), x size is: {x.shape}')

        x = x.view(x.size(0), -1)

        x = self.mocap_network.fc1(x)
        x = self.mocap_network.fc2(x)
        x = self.mocap_network.fc3(x)
        return x

    def audioForward(self, x):
        x = x.squeeze(1)
        # print(f'In Audio, after squeeze(), x size is: {x.shape}')

        # x = x.view(x.size(0), -1)
        x = self.audio_network.conv2d_1(x)
        x = self.audio_network.maxPool2d_1(x)

        x = x.view(x.size(0), -1)

        x = self.audio_network.fc1(x)
        x = self.audio_network.fcn(x)
        return x


class multimodalClassifier(basicClassifier):
    def __init__(self, input_folder, filter_folder, number_of_classes=21,
                 step=4, nframes=5, block_size=36, batch_size=42, pretrained=False):
        basicClassifier.__init__(self, input_folder, filter_folder, number_of_classes,
									 step, nframes, batch_size, 'mocap', pretrained)


        self.dlength = 183

        self.block_size = block_size    # size of a bounding box surrouding each hand

        self.input_size['color'] = [self.nframes, self.block_size, self.block_size]
        self.input_size['depth'] = self.input_size['color']
        self.input_size['mocap'] = [self.nframes, self.dlength]
        self.input_size['audio'] = [9, 40]

        # self.modality_list = ['mocap']
        # self.hand_list['both'] = self.modality_list


        self.number_of_classes = 21

        # Paths
        self.filters_file = filter_folder + 'skeletonClassifier_step' + str(step) + '.npz'

        # Training parameters
        self.learning_rate_value = 0.2
        self.learning_rate_decay = 0.9995
        self.n_epochs = 5000

        # [Xiao] 用于保存模型
        self.model_name = 'multimodalClassifier'

        # [Xiao] 指定与训练的权重文件位置
        pretrainedFolder = 'checkpoints/'
        self.pretrainedPaths = {}
        self.pretrainedPaths['video'] = pretrainedFolder + 'videoClassifier.pth'
        self.pretrainedPaths['mocap'] = pretrainedFolder + 'skeletonClassifier.pth'
        self.pretrainedPaths['audio'] = pretrainedFolder + 'audioClassifier.pth'
        self.pretrainedPaths['videoFeat'] = pretrainedFolder + 'videoFeatureExtractor.pth'
        self.pretrainedPaths['multimodal'] = pretrainedFolder + 'multimodalClassifier.pth'



    # [Xiao]
    def build_network(self, input_var = None, batch_size = None):
        if not input_var is None:
            self.sinputs = input_var
        if not batch_size is None:
            self.batch_size = batch_size

        # 构建网络，在这里 new 一个 Net 对象
        self.network = MultimodalNet(self.number_of_classes, pretrainedPaths=self.pretrainedPaths)
        self.model = self.network


        return self.network






