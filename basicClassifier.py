import torch
import collections
import numpy
import time
from datasetBasic import DatasetBasic
from datasetVideoFeatureExtractor import DatasetVideoFeatureExtractor
from torch import nn
from torch.utils.data import DataLoader
# from torch.autograd import Variable as V
from utils.visualize import Visualizer
import glob
import visdom

import os
os.environ['http_proxy'] = ''   # This line for preventing Visdom from not showing anything.


current_time=time.strftime("%Y%m%d_%H%M%S")+"_"+str(numpy.random.randint(100000))

class basicClassifier(object):
    def __init__(self, input_folder, filter_folder, number_of_classes=21,
				 step=4, nframes=5, batch_size=42, modality='mocap', pretrained=False
                 ):
        self.signature = current_time

        # Input parameters
        self.nclasses = number_of_classes
        self.step = step
        self.nframes = nframes
        self.seq_per_class = 700 # 200

        self.modality = modality
        self.hand_list = collections.OrderedDict()
        self.input_size = {}
        self.params = []

        self.dataset = {}
        self.dataset['train'] = {}
        self.dataset['valid'] = {}
        self.dataset['test'] = {}
        self.data_list = {}

        # # Theano variables
        # tensor4 = T.TensorType(theano.config.floatX, (False,) * 4)
        # tensor5 = T.TensorType(theano.config.floatX, (False,) * 5)

        # Network parameters
        self.conv_layers = []
        self.pooling = []
        self.fc_layers = []
        self.dropout_rates = []
        self.activation = 'relu'
        self.use_bias = True
        self.mask_weights = None
        self.mask_biases = None

        # Training parameters
        # lasagne.random.set_rng(numpy.random.RandomState(1234))  # a fixed seed to reproduce results
        # self.batch_size = 42
        self.pretrained = pretrained
        # self.learning_rate_value = 0.05
        # self.learning_rate_decay = 0.999
        # self.epoch_counter = 1

        # Paths
        self.search_line = "*_g%02d*.pickle"
        self.input_folder = input_folder
        self.train_folder = self.input_folder + modality + '/train/'
        self.valid_folder = self.input_folder + modality + '/valid/'
        self.test_folder = self.input_folder + modality + '/test/'
        self.filter_folder = filter_folder
        self.filters_file = filter_folder + modality + 'Classifier_step' + str(step) + '.npz'

        self.modality = modality



    def train_torch(self, datasetTypeCls, learning_rate_value=None, learning_rate_decay=None, num_epochs=5000):
        # Load dataset

        self.saved_params = []



        if self.pretrained:
            print('Saved model found. Loading...')
            self.load_model()

        if learning_rate_value is None:
            learning_rate_value = self.learning_rate_value
        if learning_rate_decay is None:
            learning_rate_decay = self.learning_rate_decay

        # Create neural network model (depending on first command line parameter)
        print("Building model and compiling functions...")

        # print(self.sinputs) # ??????? 弄啥嘞？


        # [Xiao]
        vis = Visualizer('xiao-moddrop')

        # step 1: setup model
        model = self.model
        # model = model.cuda()

        # step 2: data\
        # train_data = DatasetVideoFeatureExtractor(self.input_folder, self.modality, 'train', self.hand_list, self.seq_per_class,
        #                                           self.nclasses, self.input_size, self.step, self.nframes)
        # val_data = DatasetVideoFeatureExtractor(self.input_folder, self.modality, 'valid', self.hand_list, 200,
        #                                         self.nclasses, self.input_size, self.step, self.nframes)
        train_data = datasetTypeCls(self.input_folder, self.modality, 'train', self.hand_list,
                                                  self.seq_per_class,
                                                  self.nclasses, self.input_size, self.step, self.nframes)
        val_data = datasetTypeCls(self.input_folder, self.modality, 'valid', self.hand_list, 200,
                                                self.nclasses, self.input_size, self.step, self.nframes)

        print('Dataset prepared.')

        # self._load_dataset('train')  # ？？
        train_loader = DataLoader(train_data, batch_size=42, shuffle=True, num_workers=56)  # num_workers 按 CPU 逻辑核数目来。查看命令是： cat /proc/cpuinfo| grep "processor"| wc -l
        val_loader = DataLoader(val_data, batch_size=42, shuffle=False, num_workers=56)

        print('DataLoader prepared.')
        # val_loader = DataLoader(self.val_data, 32)

        # step 3: criterion and optimizer
        self.criterion = nn.CrossEntropyLoss()
        self.lr = 0.02 # 0.001
        self.optimizer = torch.optim.SGD(model.parameters(), lr=self.lr, weight_decay=1-0.9998, nesterov=True, momentum=0.8)

        # visdom show line of loss
        win = vis.line(
            X=numpy.array([0, 1]),
            Y=numpy.array([0, 1]),
            name="loss"
        )
        win1 = vis.line(
            X=numpy.array([0, 1]),
            Y=numpy.array([0, 1]),
            name="loss_epoch"
        )

        # step 4: go to GPU
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        model.to(self.device)


        print('Training begin...')
        # for data in train_loader:
        #     print(data[1])
        #     # break
        # print('HH=======25-20947489THRLGIHRSGHRNKGNREOSG========')
        best_val_loss = self.nclasses

        for epoch in range(num_epochs):


            # In each epoch, we do a full pass over the training data:
            losses = []

            for ii, (data, label) in enumerate(train_loader):
            # for ii, data in enumerate(train_loader):


                # print(label)
                # if(ii == 15):
                # print(len(data))
                # print(data)
                # vis.images(data[0][0], win='train_data_loader_color', opts=dict(title='SHOW IMGS!', caption='Clearlove7777.'))
                # vis.images(data[0][1], win='train_data_loader_depth', opts=dict(title='SHOW IMGS!', caption='Clearlove7777.'))
                # vis.text(str(label))

                # print(label)

                # break
                # vis.images(data[0], win='test_data_loader', opts=dict(title='SHOW IMGS!', caption='Clearlove7777.'))
                # 训练吧兄弟！
                input = data
                target = label.to(torch.int64)

                # input = input.cuda()
                # target = target.cuda()
                input, target = input.to(self.device), target.to(self.device)

                # print(f'input.shape is : {input.shape}')
                # print(f'target.shape is : {target.shape}')

                # Create a loss expression for training, i.e., a scalar objective we want
                # to minimize (for our multi-class problem, it is the cross-entropy loss):
                self.optimizer.zero_grad()
                score = model(input)
                # print(f'score shape is: {score.shape}')
                loss = self.criterion(score, target)

                loss.backward()
                self.optimizer.step()

                losses.append(loss.data)



                # print(f'score is : {score}')
                # print(f'target is : {target}')

                # print(f'loss.data is: {loss.data}')
                # print(f'numpy.array(loss.data) is : {numpy.array(loss.data)}')

                # if ii % 10 == 0:
                #     vis.plot('loss', loss)
                vis.line(X=torch.Tensor([ii + epoch*len(train_loader)]), Y=torch.Tensor([loss]), win=win, update='append', name='train_loss')
                # vis.line(X=t.Tensor([ii]), Y=t.Tensor([ii]), win=win, update='append')
                # vis.updateTrace(X=numpy.array([ii]), Y=numpy.array(loss.data), win=win, name='train_loss')

            # 计算验证集上的指标及可视化
            val_loss = self.val(model, val_loader)
            # 若验证误差降低，更新最好模型
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                self.save_model()
            # vis.plot('val_loss', val_loss)

            vis.line(X=torch.Tensor([epoch]), Y=torch.Tensor([sum(losses) / len(losses)]), win=win1, update='append',
                     name='mean_train_loss_per_epoch')
            vis.line(X=torch.Tensor([epoch]), Y=torch.Tensor([val_loss]), win=win1, update='append',
                     name='val_loss')

            vis.log("[Train Loss] epoch:{epoch},lr:{lr},loss:{loss}".format(
                epoch=epoch, loss=loss.data,
                lr=self.lr))
            vis.log("[Valid Loss] epoch:{epoch},lr:{lr},loss:{loss}".format(
                epoch=epoch, loss=val_loss,
                lr=self.lr))


    def _prepare_inputs(self, subset, ind):
        """
        Function to sample and concatenate inputs for each minibatches,
        used with pickle files.

        :type subset: str
        :param subset: data subset ("train", "valid" or "test")

        :type ind: int
        :param ind: minibatch index
        """

        inputs = []

        # Append data from all channels

        for hnd in self.hand_list:
            for mdlt in self.hand_list[hnd]:
                inputs.append(self.dataset[subset][hnd][mdlt][ind * self.batch_size:
                                                              (ind + 1) * self.batch_size])
        if subset in ['train', 'valid']:
            inputs.append(self.dataset[subset]['labels'][ind * self.batch_size:
                                                         (ind + 1) * self.batch_size])
        return inputs
        # this is a list of tuples of size (batch_size, channel=1, input_size)


    def val(self, model, dataloader):
        """
        计算模型在验证集上的准确率等信息
        """

        # 把模型设为验证模式
        model.eval()

        losses = []

        for ii, data in enumerate(dataloader):
            input, label = data
            val_input = input.to(self.device)
            val_label = label.to(self.device)
            score = model(val_input)
            losses.append(self.criterion(score, val_label).data)

        # 把模型恢复为训练模式
        model.train()

        loss = sum(losses) / len(losses)
        return loss


    def save_model(self, name = None):
        if name is None:
            name = 'checkpoints/' + self.model_name + '.pth'
        torch.save(self.network.state_dict(), name)
        return name