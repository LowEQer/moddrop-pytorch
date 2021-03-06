# from torchvision import transforms
from datasets.datasetVideoClassifier import DatasetVideoClassifier
from datasets.datasetSkeleton import DatasetSkeleton
from datasets.datasetAudio import DatasetAudio

import random
from datasets.datasetBasic import DatasetBasic
import os
os.environ['http_proxy'] = ''   # This line for preventing Visdom from not showing anything.

class DatasetMultimodal_0(DatasetBasic):

    def __init__(self, input_folder, modality, subset, hand_list, seq_per_class, nclasses, input_size, step, nframes):
        """
        :type subset: string
		:param subset: string representing 'train', 'validation' or 'test' subsets
        """

        if subset == 'train':
            self.seq_per_class = seq_per_class
        else:   # valid or test
            self.seq_per_class = seq_per_class // 10

        # 各模态数据集类
        self.datasetTypes = {
            'color': DatasetVideoClassifier(input_folder, 'color', subset, hand_list,
                                            self.seq_per_class,
                                                  nclasses, input_size, step, nframes),
            'mocap': DatasetSkeleton(input_folder, 'mocap', subset, hand_list,
                                     self.seq_per_class,
                                                  nclasses, input_size, step, nframes),
            'audio': DatasetAudio(input_folder, 'audio', subset, hand_list,
                                  self.seq_per_class,
                                                  nclasses, input_size, step, nframes),
        }

        self.dataset_length = min(len(self.datasetTypes['color']), len(self.datasetTypes['mocap']), len(self.datasetTypes['audio']))

        search_line = "*_g%02d*.pickle"

        modality_list = ['color','depth','mocap','audio']
        hand_list['right'] = ['color', 'depth']
        hand_list['left'] = ['color', 'depth']
        hand_list['both'] = ['mocap', 'audio']

        self.nclasses = nclasses
        self.subset = subset

        # DatasetBasic.__init__(self, input_folder, modality, subset, hand_list, seq_per_class, nclasses, input_size, step, nframes, modality_list, search_line, block_size=36)

    def __getitem__(self, ind):
        """


        :param index:
        :return:
        """
        subset = self.subset
        sample = {}
        label = 99

        # if subset in ['train', 'valid']:
        #     # label.append(self.dataset[subset]['labels'][ind])
        #     label = self.dataset[subset]['labels'][ind]

        sample['video'], _ = self.datasetTypes['color'][ind]
        sample['mocap'], _ = self.datasetTypes['mocap'][ind]
        sample['audio'], label = self.datasetTypes['audio'][ind]


        return sample, int(label)

    def __len__(self):
        # return 42
        # return self.seq_per_class * self.nclasses
        return self.dataset_length

    def _get_stblock(self, data_input, hnd, mdlt, start_frame=None):
        """
        取一个时间块。即取一个5帧的块。stblock，意为space time block
        :param data_input:
        :param hnd:
        :param mdlt:
        :param start_frame:
        :return:
        """
        if start_frame is None:
            start_frame = random.randint(0, len(data_input)
                                         - self.step * (self.nframes - 1) - 1)
        if not mdlt == 'depth':
            stblock = self.datasetTypes[mdlt]._get_stblock(data_input,
                                                          hnd, mdlt, start_frame)
        else:
            stblock = self.datasetTypes['color']._get_stblock(data_input,
                                                             hnd, mdlt, start_frame)
        return stblock


    def _load_file(self, file_name, data_sample=None):

        data_sample = {}
        # print file_name
        for mdlt, dataset in self.datasetTypes.items():
            data_sample[mdlt] = dataset._load_file(file_name, None)
        return data_sample


