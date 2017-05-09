# coding=utf-8
from __future__ import print_function, absolute_import

# global scope
from keras.callbacks import TensorBoard, ModelCheckpoint
from keras import backend as K
import json
import numpy as np
import os
import sys
sys.path.append("src/models")

# project scope
from data.data_loader import load_data, batched
from data import datasets
from models import enet as model
print("the model is loaded")

def callbacks(log_dir, checkpoint_dir, model_name):
    """ 
    :param log_dir: 
    :param checkpoint_dir: 
    :param model_name: 
    :return: 
    """
    # TODO: Add ReduceLROnPlateau callback
    cbs = []

    tb = TensorBoard(log_dir=log_dir,
                     histogram_freq=1,
                     # write_graph=True,
                     write_images=True)
    cbs.append(tb)

    best_model = os.path.join(checkpoint_dir, '{}_best.h5'.format(model_name))
    save_best = ModelCheckpoint(best_model, save_best_only=True)
    cbs.append(save_best)

    checkpoint_file = os.path.join(checkpoint_dir, 'weights.' + model_name + '.{epoch:02d}-{val_loss:.2f}.h5')
    checkpoints = ModelCheckpoint(filepath=checkpoint_file, verbose=1)
    cbs.append(checkpoints)

    # reduce_lr = ReduceLROnPlateau(monitor='val_loss',
    #                               factor=0.1,
    #                               patience=10,
    #                               verbose=0,
    #                               mode='auto',
    #                               epsilon=0.0001,
    #                               cooldown=0,
    #                               min_lr=0)
    # cbs.append(reduce_lr)
    return cbs


def train(solver, dataset_name):

    print('Preparing to train on {} data...'.format(dataset_name))

    epochs = solver['epochs']
    batch_size = solver['batch_size']
    completed_epochs = solver['completed_epochs']

    np.random.seed(1337)  # for reproducibility

    dw = solver['dw']
    dh = solver['dh']

    resize_mode = str(solver['resize_mode'])

    dataset = datasets.load(dataset_name)
    nc = dataset.num_classes()  # categories + background

    autoencoder, model_name = model.build(nc=nc, w=dw, h=dh)
    if 'h5file' in solver:
        h5file = solver['h5file']
        print('Loading model {}'.format(h5file))
        h5file, ext = os.path.splitext(h5file)
        autoencoder.load_weights(h5file + ext)
    else:
        autoencoder = model.transfer_weights(autoencoder)

    if K.backend() == 'tensorflow':
        print('Tensorflow backend detected; Applying memory usage constraints')
        ss = K.tf.Session(config=K.tf.ConfigProto(gpu_options=K.tf.GPUOptions(allow_growth=True)))
        K.set_session(ss)
        ss.run(K.tf.global_variables_initializer())

    print('Done loading {} model!'.format(model_name))

    experiment_dir = os.path.join('models', dataset_name, model_name)
    log_dir = os.path.join(experiment_dir, 'logs')
    checkpoint_dir = os.path.join(experiment_dir, 'weights')

    train_gen = load_data(dataset_name=dataset_name,
                          data_dir=os.path.join('data', dataset_name),
                          target_h=dh, target_w=dw,
                          data_type='train2014',
                          resize_mode=resize_mode)
    nb_train_samples = next(train_gen)
    train_gen = batched(train_gen, batch_size)
    steps_per_epoch = nb_train_samples / batch_size

    val_gen = load_data(dataset_name=dataset_name,
                        data_dir=os.path.join('data', dataset_name),
                        target_h=dh, target_w=dw,
                        data_type='val2014',
                        sample_size=nb_train_samples // 10,
                        resize_mode=resize_mode)
    nb_val_samples = next(val_gen)  # first generator item is the count
    val_gen = batched(val_gen, batch_size)
    validation_steps = nb_val_samples / batch_size

    autoencoder.fit_generator(generator=train_gen,
                              steps_per_epoch=steps_per_epoch,
                              epochs=epochs,
                              verbose=1,
                              callbacks=callbacks(log_dir, checkpoint_dir, model_name),
                              validation_data=val_gen,
                              validation_steps=validation_steps,
                              initial_epoch=completed_epochs)


if __name__ == '__main__':
    solver_json = 'config/solver.json'

    print('solver json: {}'.format(os.path.abspath(solver_json)))

    solver = json.load(open(solver_json))

    train(solver=solver, dataset_name='mscoco')
