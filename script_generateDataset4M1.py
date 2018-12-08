"""
1. generate damaged multimodal dataset and QoUs over this dataset
2. generate labels
"""
from datasetsOfLowQualityData.datasetOfDmgedMultimodalAndQoU import DatasetOfDamagedMultimodalAndQoU
from lqMultimodalClassifier import lqMultimodalClassifier
from multimodalClassifier import multimodalClassifier
from datasets.datasetMultimodal import DatasetMultimodal
from data_quality.QualityMetric import DataQuality
from data_quality.DamageFunctions import Noise
from entropyEvaluating import entropyOnProbs

from torch.utils.data import DataLoader
import pickle
import os
import itertools
import torch


def testExistAndCreateDir(s):
    path = os.path.join(os.getcwd(), s)
    if not os.path.isdir(path):
        # os.mkdir(path)
        os.makedirs(path)

def getSubsets(features):
    """
    features: list
    """
    subsets = []
    for i in range(1, len(features) + 1):
        curList = list(map(list, itertools.combinations(features, i)))
        subsets.extend(curList)
    return subsets

noise = Noise(randomly=False)    # randomly = True, 则表示以随机程度加入各类噪声, 这里置否是为了让maskNoise能够以 rate=0 来遮蔽原始数据。
                                 # 后面会再次创建另一个 Noise 实例，其用于随机加噪声，故其 randomly = True 。
def mask(sample, subset):
    '''
    借用 Noise 类中的 mask 噪声实现对整帧的屏蔽
    :param sample:
    :param subset:
    :return:
    '''
    sample = sample.copy()
    for key in sample.keys():
        if key not in subset:
            sample[key] = noise.MaskingNoise(sample[key], 0).float() # .astype(np.float32)
    return sample

source_folder = '/home/xiaoyunlong/downloads/DeepGesture/Montalbano/'
'''
	Location of the dataset (Chalearn 2014) which has been pre-processed.
'''

filter_folder = 'filters/'
classifier = multimodalClassifier(step = 4,
                                 input_folder = source_folder,
                                 filter_folder = filter_folder)

# 1. generate damaged multimodal dataset and QoUs over this dataset

"""
for s in D0:
    for u in range(r):  # randomly get r damaged data sample
        _s = {}
        QoU = []
        for mdlt in s:
            for dmg_dimension in dmg_functions:
                _s[mdlt] = dmg_func(s[mdlt])

            for score_func in score_funcs:
                QoU.append(score_func(_s[mdlt]))

        # save to disk
        cPickle(_s, QoU, label_of_s, u, if_s_name_available_then_set_it_here)
"""
def generateLQDataset(r = 8, subset = 'train'):
    # # Consts
    # r = 8   # 单条原多模态数据，生成 r 条被破坏记录
    #

    train_data = DatasetMultimodal(classifier.input_folder, '', subset, classifier.hand_list,
                                   classifier.seq_per_class,
                                   classifier.nclasses, classifier.input_size, classifier.step, classifier.nframes)
    train_loader = DataLoader(train_data, batch_size=1, shuffle=False, num_workers=56)

    dmg_functions = Noise().getDmgFunctions()
    score_functions = DataQuality().getMetricFuncs()

    for ii, (data, label) in enumerate(train_loader):
        n = len(train_loader)
        print(f'ii: {ii}, {ii/n}')

        for u in range(r):
            _s = {}
            QoU = []
            for mdlt in data.keys():
                for dmg_func in dmg_functions:
                    _s[mdlt] = dmg_func(data[mdlt].data.numpy()[0])

                for score_func in score_functions:
                    QoU.append(score_func(_s[mdlt]))

            # save to disk
            damaged_multimodal = {}
            damaged_multimodal['data'] = _s
            damaged_multimodal['QoU'] = QoU
            damaged_multimodal['label'] = label # 这里的label，是原始多模态任务中的label，如手势类别
            filename = str(label.data) + '_' + str(ii) + '_' + str(u)
            # testExistAndCreateDir('damaged_multimodal/')
            # pickle.dump(damaged_multimodal, open('damaged_multimodal/' + filename, 'wb'))
            path = 'LowQuality_'+str(r)+'_times/' + subset + '/'
            testExistAndCreateDir(path) # 原始高质量数据集的r倍数量的样本数的低质量数据
            pickle.dump(damaged_multimodal, open(path + filename, 'wb'))

# 2. generate labels

"""
for _s, QoUs in DataLoader(dataset_generated_above):
    # s_probs = set()
    Set_probs = []
    Set_modality = getSubsets([modalities])
    for subset in Set_modality:
        probs, result = M0(mask(_s, subset))
        Set_probs.append((probs, result, label, subset))

        #if result correct:  # 只有分类正确的前提下，熵低才有意义
               # 那么存在一个情况，可能分类就都不正确啊...

    sort Set_probs by (-correct, H(probs)) # ascend
    # 取第一个

    # if Set_probs is empty:
    #     subset_best =
    # else:
    #     subset_best = argminH(Set_probs)

    # save to disk
    cPickle(QoUs, subset_best)

    # or save in memory
    df(dtypes = {'subset_best': str, others: float})
"""
def generateDeltaStar(r = 8, train_valid_test = 'train', path_D_R_root = 'D_R'):
    path = 'LowQuality_' + str(r) + '_times/' + train_valid_test + '/'
    path_D_R = path_D_R_root + '/' + train_valid_test + '/'

    # dataset_damaged_multimodal = DatasetOfDamagedMultimodal(os.path.join(os.getcwd(), 'damaged_multimodal/'))
    dataset_damaged_multimodal_and_qou = DatasetOfDamagedMultimodalAndQoU(os.path.join(os.getcwd(), path), train_valid_test)
    dataset_generated_above = DataLoader(dataset_damaged_multimodal_and_qou, batch_size=1, shuffle=False, num_workers=8)

    # 预备下面要用的方法
    M0 = lqMultimodalClassifier(step = 4,
                                     input_folder = source_folder,
                                     filter_folder = filter_folder)
    H = entropyOnProbs  # 根据概率向量求熵

    # 预备好M0，加载已训练的权重，进入预测模式（非训练模式，一方面保证权重不更新，一方面保证batchnorm可以在batchsize为1时正常工作）并挪上GPU
    M0.build_network() # build the model
    M0.load_weights()
    M0.model.eval()
    M0.model.to(M0.device)

    with torch.no_grad():
        for ii, (_s, label, QoU) in enumerate(dataset_generated_above):
            label = label.data.cpu().numpy()

            n = len(dataset_generated_above)
            print(f'ii: {ii}, {ii/n}')

            Set_probs = []
            modalities = _s.keys()
            Set_modality = getSubsets(list(modalities))

            # # DEBUG
            # print(f'_s type: ')

            # # DEBUG
            # for mdlt in _s.keys():
            #     _s[mdlt] = _s[mdlt].unsqueeze(0)

            for subset in Set_modality:
                probs = M0.model(mask(_s, subset))    # probs 即为模型输出的 score（见 basicClassifier.py 中 test 相关方法）
                result = torch.argmax(probs.data, dim=1)
                Set_probs.append((probs.data.cpu().numpy()[0], label, result, subset))

            Set_probs.sort(key=lambda x: (x[1]!=x[2], H(x[0])))
            subset_best = Set_probs[0][3]

            sample_for_M1 = {}
            sample_for_M1['QoU'] = QoU#.data.cpu().numpy()[0]
            sample_for_M1['subset_best'] = subset_best
            filename = str(label) + '_' + str(ii)
            # testExistAndCreateDir('train_for_M1/')
            # pickle.dump(sample_for_M1, open('train_for_M1/' + filename, 'wb'))
            testExistAndCreateDir(path_D_R)
            pickle.dump(sample_for_M1, open(path_D_R + filename, 'wb'))



# 3. Train M1
#
# M1 实现为 nn.Module 子类，两层神经网络
"""

"""


# 4. Use M1
#
# 输入
#   s: dict, 多模态数据
# 输出
#   result: 手势识别结果（类别）
"""
QoU = []
for mdlt in s:
    for score_func in score_funcs:
        QoU.append(score_func(_s[mdlt]))
subset_best = M1(QoU)
masked_s = mask(s, subset_best)    # subset: list, s: dict(key: mdlt)

result = M0(masked_s)
"""