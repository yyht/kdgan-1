from kdgan import config, metric, utils
from dis_model import DIS
from gen_model import GEN

import math
import os
import time

import numpy as np
import tensorflow as tf

from os import path
from tensorflow.contrib import slim

tf.app.flags.DEFINE_float('beta', 0.3, '')
tf.app.flags.DEFINE_float('dis_weight_decay', 0.0, 'l2 coefficient')
tf.app.flags.DEFINE_float('dropout_keep_prob', 0.5, '')
tf.app.flags.DEFINE_float('gen_weight_decay', 0.001, 'l2 coefficient')
tf.app.flags.DEFINE_float('init_learning_rate', 0.001, '')
tf.app.flags.DEFINE_float('learning_rate_decay_factor', 1.0, '')
tf.app.flags.DEFINE_float('num_epochs_per_decay', 10.0, '')
tf.app.flags.DEFINE_float('tch_weight_decay', 0.00001, 'l2 coefficient')
tf.app.flags.DEFINE_float('temperature', 3.0, '')

tf.app.flags.DEFINE_integer('cutoff', 3, '')
tf.app.flags.DEFINE_integer('feature_size', 4096, '')
tf.app.flags.DEFINE_integer('num_epoch', 20, '')
tf.app.flags.DEFINE_integer('num_dis_epoch', 10, '')
tf.app.flags.DEFINE_integer('num_gen_epoch', 5, '')

tf.app.flags.DEFINE_string('gen_model_ckpt', None, '')
tf.app.flags.DEFINE_string('model_name', None, '')

flags = tf.app.flags.FLAGS
flags.num_epochs_per_decay *= flags.num_dis_epoch

num_batch_t = int(flags.num_epoch * config.train_data_size / config.train_batch_size)
eval_interval = int(config.train_data_size / config.train_batch_size)
print('tn:\t#batch=%d\neval:\t#interval=%d' % (num_batch_t, eval_interval))

global_step = tf.train.create_global_step()
dis_t = DIS(flags, is_training=True)
gen_t = GEN(flags, is_training=True)
scope = tf.get_variable_scope()
scope.reuse_variables()
dis_v = DIS(flags, is_training=False)
gen_v = GEN(flags, is_training=False)

def generate_dis_sample(label_dat, label_gen):
  # print('{0} {1:.2f}'.format(label_dat.shape, label_dat.sum()))
  # print('{0} {1:.2f}'.format(label_gen.shape, label_gen.sum()))
  sample_np, label_np = [], []
  for batch, (label_d, label_g) in enumerate(zip(label_dat, label_gen)):
    num_sample = np.count_nonzero(label_d)
    # print(batch, label_d.shape, label_g.shape, num_sample)
    sample_d = np.random.choice(config.num_label, num_sample, p=label_d)
    for sample in sample_d:
      # print(batch, sample, 1.0)
      sample_np.append((batch, sample))
      label_np.append(1.0)
    sample_g = np.random.choice(config.num_label, num_sample, p=label_g)
    for sample in sample_g:
      sample_np.append((batch, sample))
      label_np.append(0.0)
  sample_np = np.asarray(sample_np)
  label_np = np.asarray(label_np)
  # for sample, label in zip(sample_np, label_np):
  #   print(sample, label)
  return sample_np, label_np

def generate_gen_sample(label_dat, label_gen):
  sample_np = []
  for batch, (label_d, label_g) in enumerate(zip(label_dat, label_gen)):
    num_sample = np.count_nonzero(label_d) * 2
    # print(num_sample, label_g.sum())
    # if abs(label_g.sum() - 1.0) > 0.001:
    #   print(label_g)
    #   exit()
    sample_g = np.random.choice(config.num_label, num_sample, p=label_g)
    for sample in sample_g:
      # if (sample < 0) or (sample > config.num_label - 1):
      #   print(sample_g)
      #   exit()
      sample_np.append((batch, sample))
  sample_np = np.asarray(sample_np)
  return sample_np

def main(_):
  for variable in tf.trainable_variables():
    num_params = 1
    for dim in variable.shape:
      num_params *= dim.value
    print('{}\t({} params)'.format(variable.name, num_params))

  data_sources_t = utils.get_data_sources(flags, is_training=True)
  data_sources_v = utils.get_data_sources(flags, is_training=False)
  print('tn: #tfrecord=%d\nvd: #tfrecord=%d' % (len(data_sources_t), len(data_sources_v)))
  
  ts_list_d = utils.decode_tfrecord(flags, data_sources_t, shuffle=True)
  bt_list_d = utils.generate_batch(ts_list_d, config.train_batch_size)
  user_bt_d, image_bt_d, text_bt_d, label_bt_d, file_bt_d = bt_list_d

  ts_list_g = utils.decode_tfrecord(flags, data_sources_t, shuffle=True)
  bt_list_g = utils.generate_batch(ts_list_g, config.train_batch_size)
  user_bt_g, image_bt_g, text_bt_g, label_bt_g, file_bt_g = bt_list_g

  ts_list_v = utils.decode_tfrecord(flags, data_sources_v, shuffle=False)
  bt_list_v = utils.generate_batch(ts_list_v, config.valid_batch_size)

  best_hit_v = -np.inf
  start = time.time()
  init_op = tf.global_variables_initializer()
  with tf.Session() as sess:
    sess.run(init_op)
    writer = tf.summary.FileWriter(config.logs_dir, graph=tf.get_default_graph())
    gen_t.saver.restore(sess, flags.gen_model_ckpt)
    with slim.queues.QueueRunners(sess):
      image_hit_v = utils.evaluate(flags, sess, gen_v, bt_list_v)
      print('init\thit={0:.4f}'.format(image_hit_v))

      batch_d, batch_g = -1, -1
      for epoch in range(flags.num_epoch):
        for dis_epoch in range(flags.num_dis_epoch):
          print('epoch %03d dis_epoch %03d' % (epoch, dis_epoch))
          num_batch_d = math.ceil(config.train_data_size / config.train_batch_size)
          for _ in range(num_batch_d):
            batch_d += 1
            image_np_d, label_dat_d = sess.run([image_bt_d, label_bt_d])
            # print(image_np_d.shape, label_dat_d.shape)
            feed_dict = {gen_t.image_ph:image_np_d}
            label_gen_d, = sess.run([gen_t.labels], feed_dict=feed_dict)
            # print(label_gen_d.shape, type(label_gen_d))
            sample_np_d, label_np_d = generate_dis_sample(label_dat_d, label_gen_d)
            feed_dict = {
              dis_t.image_ph:image_np_d,
              dis_t.sample_ph:sample_np_d,
              dis_t.label_ph:label_np_d,
            }
            sess.run(dis_t.train_op, feed_dict=feed_dict)
            # _, summary = sess.run([dis_t.train_op, dis_t.summary_op], feed_dict=feed_dict)
            # writer.add_summary(summary, batch_d)

            # if (batch_d + 1) % eval_interval != 0:
            #   continue
            # image_hit_v = utils.evaluate(flags, sess, dis_v, bt_list_v)
            # tot_time = time.time() - start
            # print('#%d hit=%.4f (%.0fs)' % (batch_d, image_hit_v, tot_time))

        for gen_epoch in range(flags.num_gen_epoch):
          # print('epoch %03d gen_epoch %03d' % (epoch, gen_epoch))
          num_batch_g = math.ceil(config.train_data_size / config.train_batch_size)
          for _ in range(num_batch_g):
            batch_g += 1
            image_np_g, label_dat_g = sess.run([image_bt_g, label_bt_g])
            # print(image_np_g.shape, label_dat_g.shape)
            feed_dict = {gen_t.image_ph:image_np_g}
            label_gen_g, = sess.run([gen_t.labels], feed_dict=feed_dict)
            sample_np_g = generate_gen_sample(label_dat_g, label_gen_g)
            feed_dict = {
              dis_t.image_ph:image_np_g,
              dis_t.sample_ph:sample_np_g,
            }
            reward_np_g, = sess.run([dis_t.rewards], feed_dict=feed_dict)
            # for sample, reward in zip(sample_np_g, reward_np_g):
            #   print(sample, reward)
            feed_dict = {
              gen_t.image_ph:image_np_g,
              gen_t.sample_ph:sample_np_g,
              gen_t.reward_ph:reward_np_g,
            }
            _, summary = sess.run([gen_t.gan_train_op, gen_t.summary_op],
                feed_dict=feed_dict)
            if batch_g % 20 == 0:
              writer.add_summary(summary, batch_g)
            if (batch_g + 1) % eval_interval != 0:
              continue
            image_hit_v = utils.evaluate(flags, sess, gen_v, bt_list_v)
            tot_time = time.time() - start
            print('#%d hit=%.4f (%.0fs)' % (batch_g, image_hit_v, tot_time))
          # break
        image_hit_v = utils.evaluate(flags, sess, gen_v, bt_list_v)
        print('final\thit={0:.4f}'.format(image_hit_v))
        # break

if __name__ == '__main__':
  tf.app.run()





