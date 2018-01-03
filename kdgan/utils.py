from kdgan import config

import numpy as np
import tensorflow as tf

from preprocessing import preprocessing_factory
from tensorflow.contrib import slim

def save_collection(coll, outfile):
    with open(outfile, 'w') as fout:
        for elem in coll:
            fout.write('%s\n' % elem)

def load_collection(infile):
    with open(infile) as fin:
        coll = [elem.strip() for elem in fin.readlines()]
    return coll

def load_sth_to_id(infile):
    with open(infile) as fin:
        sth_list = [sth.strip() for sth in fin.readlines()]
    sth_to_id = dict(zip(sth_list, range(len(sth_list))))
    return sth_to_id

def load_label_to_id():
    label_to_id = load_sth_to_id(config.label_file)
    return label_to_id

def load_token_to_id():
    vocab_to_id = load_sth_to_id(config.vocab_file)
    return vocab_to_id

def load_id_to_sth(infile):
    with open(infile) as fin:
        sth_list = [sth.strip() for sth in fin.readlines()]
    id_to_sth = dict(zip(range(len(sth_list)), sth_list))
    return id_to_sth

def load_id_to_label():
    id_to_label = load_id_to_sth(config.label_file)
    return id_to_label

def load_id_to_token():
    id_to_vocab = load_id_to_sth(config.vocab_file)
    return id_to_vocab

def decode_tfrecord(tfrecord_file, shuffle=True):
    Tensor = slim.tfexample_decoder.Tensor
    Image = slim.tfexample_decoder.Image
    TFExampleDecoder = slim.tfexample_decoder.TFExampleDecoder
    Dataset = slim.dataset.Dataset
    DatasetDataProvider = slim.dataset_data_provider.DatasetDataProvider

    data_sources = [tfrecord_file]
    num_label = config.num_label
    token_to_id = load_token_to_id()
    unk_token_id = token_to_id[config.unk_token]
    reader = tf.TFRecordReader
    keys_to_features = {
        config.user_key:tf.FixedLenFeature((), tf.string,
                default_value=''),
        config.image_encoded_key:tf.FixedLenFeature((), tf.string,
                default_value=''),
        config.text_key:tf.VarLenFeature(dtype=tf.int64),
        config.label_key:tf.FixedLenFeature([num_label], tf.int64,
                default_value=tf.zeros([num_label], dtype=tf.int64)),
        config.image_format_key:tf.FixedLenFeature((), tf.string,
                default_value='jpg'),
        config.image_file_key:tf.FixedLenFeature((), tf.string,
                default_value='')
    }
    print(unk_token_id)
    items_to_handlers = {
        'user':Tensor(config.user_key),
        'image':Image(),
        'text':Tensor(config.text_key, default_value=unk_token_id),
        'label':Tensor(config.label_key),
        'image_file':Tensor(config.image_file_key),
    }
    decoder = TFExampleDecoder(keys_to_features, items_to_handlers)
    num_samples = np.inf
    items_to_descriptions = {
        'user':'',
        'image':'',
        'text':'',
        'label':'',
        'image_file':'',
    }
    dataset = Dataset(
        data_sources=data_sources,
        reader=reader,
        decoder=decoder,
        num_samples=num_samples,
        items_to_descriptions=items_to_descriptions,
    )
    provider = DatasetDataProvider(dataset, shuffle=shuffle)
    ts_list = provider.get(['user', 'image', 'text', 'label', 'image_file'])
    return ts_list

def generate_batch(model, ts_list, batch_size):
    get_preprocessing = preprocessing_factory.get_preprocessing
    preprocessing = get_preprocessing(model.preprocessing_name,
            is_training=model.is_training)
    user_ts, image_ts, text_ts, label_ts, image_file_ts = ts_list
    image_ts = preprocessing(image_ts, model.image_size, model.image_size)
    user_bt, image_bt, text_bt, label_bt, image_file_bt = tf.train.batch(
            [user_ts, image_ts, text_ts, label_ts, image_file_ts], 
            batch_size=batch_size,
            dynamic_pad=True,
            num_threads=config.num_threads)
    return user_bt, image_bt, text_bt, label_bt, image_file_bt







