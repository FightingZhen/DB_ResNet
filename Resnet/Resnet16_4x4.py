import tensorflow as tf
import Transform_Data_v1 as td
import numpy as np
import time
import os

# Weight Initializer is xavier initializer

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

config=tf.ConfigProto()
config.gpu_options.allow_growth=True
sess=tf.InteractiveSession(config=config)

Epoch = 300
Test_epoch=10
L2_parameter=5e-4
start_learning_rate = 1e-3
constant_initializer_parameter=0.01
decay_rate=0.98
dropout_rate = 0.8

max_val_accuracy=0.0
counter=0

training_batch_size = 128
test_batch_size = 128

Load_Data=False
Training=True
Early_stop=False
initializer_uniform = True

model_name='Resnet16_4x4'
checkpoint_dir='D:/Checkpoint_new/'+model_name+'/'

len_training_data, validation, test = td.Initialization(test_batch_size)
iteration_time = int(len_training_data / training_batch_size)

with tf.name_scope('Learning_Rate'):
    global_step=tf.Variable(0)
    learning_rate=tf.train.exponential_decay(start_learning_rate,global_step,iteration_time,decay_rate,staircase=True,name='learning_rate')
    tf.summary.scalar(' ',learning_rate)

def leaky_relu(x, alpha=0.9):
    with tf.variable_scope('Leaky_Relu'):
        return tf.nn.relu(x)-alpha*tf.nn.relu(-x)

def single_layer(input, in_channel, out_channel, conv_ksize, layer_name, relu=False, trans=False):
    with tf.variable_scope(layer_name):
        weight = tf.get_variable('weight', [conv_ksize, conv_ksize, in_channel, out_channel],initializer=tf.contrib.layers.xavier_initializer(uniform=initializer_uniform))
        tf.add_to_collection('losses',tf.contrib.layers.l2_regularizer(L2_parameter)(weight))
        bias = tf.get_variable('bias', [out_channel], initializer=tf.constant_initializer(constant_initializer_parameter))
        if trans == True:
            conv = tf.nn.bias_add(tf.nn.conv2d(input, weight, strides=[1, 2, 2, 1], padding='SAME'), bias)
        else:
            conv = tf.nn.bias_add(tf.nn.conv2d(input, weight, strides=[1, 1, 1, 1], padding='SAME'), bias)
        conv_result = tf.layers.batch_normalization(conv)
        tf.summary.histogram(' ',conv_result)
        if relu == True:
            conv_result=tf.nn.relu(conv_result)
    return conv_result

def trans_dimension_image(input, in_channel, out_channel, trans_name):
    with tf.variable_scope(trans_name):
        weight = tf.get_variable('weight', [1, 1, in_channel, out_channel],initializer=tf.contrib.layers.xavier_initializer(uniform=initializer_uniform))
        tf.add_to_collection('losses', tf.contrib.layers.l2_regularizer(L2_parameter)(weight))
        bias=tf.get_variable('bias',[out_channel],initializer=tf.constant_initializer(constant_initializer_parameter))
        result = tf.nn.bias_add(tf.nn.conv2d(input, weight, strides=[1, 2, 2, 1], padding='SAME'),bias)
    return result

def trans_dimension(input, in_channel, out_channel, trans_name):
    with tf.variable_scope(trans_name):
        weight = tf.get_variable('weight', [1, 1, in_channel, out_channel],initializer=tf.contrib.layers.xavier_initializer(uniform=initializer_uniform))
        tf.add_to_collection('losses', tf.contrib.layers.l2_regularizer(L2_parameter)(weight))
        bias = tf.get_variable('bias', [out_channel], initializer=tf.constant_initializer(constant_initializer_parameter))
        result = tf.nn.bias_add(tf.nn.conv2d(input, weight, strides=[1, 1, 1, 1], padding='SAME'),bias)
    return result

def block(input, in_channel, out_channel1, out_channel2, conv_ksize, Block_name, image_trans=False, dimention_trans=False):
    trans_input,B_layer1=[],[]
    if image_trans == True:
        trans_input = trans_dimension_image(input,in_channel,out_channel2,Block_name+'/trans')
        B_layer1 = single_layer(input, in_channel, out_channel1, conv_ksize, Block_name + '/layer1', relu=True, trans=True)

    if image_trans == False and dimention_trans == True:
        trans_input = trans_dimension(input, in_channel, out_channel2, Block_name+'/trans')
        B_layer1 = single_layer(input, in_channel, out_channel1, conv_ksize, Block_name + '/layer1', relu=True, trans=False)

    if image_trans == False and dimention_trans == False:
        trans_input = input
        B_layer1 = single_layer(input, in_channel, out_channel1, conv_ksize, Block_name + '/layer1', relu=True, trans=False)

    B_layer2=single_layer(B_layer1,out_channel1,out_channel2,conv_ksize, Block_name+'/layer2', relu=False, trans=False)

    result_summary = tf.add(trans_input,B_layer2)

    return result_summary

def section(input, in_channel, out_channel1, out_channel2, conv_ksize, section_name, block_num, image_trans=False, dimention_trans=False):
    with tf.variable_scope(section_name):
        block_result = block(input,in_channel,out_channel1,out_channel2,conv_ksize,'block1',image_trans=image_trans,dimention_trans=dimention_trans)
        for i in range(block_num-1):
            block_result = block(block_result,out_channel2,out_channel1,out_channel2,conv_ksize,'block'+str(i+2),image_trans=False,dimention_trans=False)
        block_result=tf.nn.dropout(block_result,keep_prob=keep_prob)
    return block_result

def f_value(matrix):
    f = 0.0
    length = len(matrix[0])
    for i in range(length):
        recall = matrix[i][i] / np.sum([matrix[i][m] for m in range(7)])
        precision = matrix[i][i] / np.sum([matrix[n][i] for n in range(7)])
        result = (recall*precision) / (recall+precision)
        print(result)
        f += result
    f *= (2/7)
    return f

def test_procedure():
    confusion_matrics=np.zeros([7,7],dtype="int")

    for k in range(len(test)):
        matrix_row, matrix_col = sess.run(distribution, feed_dict={x: test[k][0], y_: test[k][1], keep_prob:1.0})
        for m, n in zip(matrix_row, matrix_col):
            confusion_matrics[m][n] += 1

    test_accuracy=float(np.sum([confusion_matrics[q][q] for q in range(7)])/np.sum(confusion_matrics))
    detail_test_accuracy = [confusion_matrics[i][i]/np.sum(confusion_matrics[i]) for i in range(7)]
    log1 = "Test Accuracy : %g" % test_accuracy
    log2 = np.array(confusion_matrics.tolist())
    log3= ''
    for j in range(7):
        log3 += 'category %g test accuracy : %g\n' % (j,detail_test_accuracy[j])
    logfile = open(checkpoint_dir + model_name+ '.txt', 'a+')
    log4 = 'F_Value : %g' % f_value(confusion_matrics)
    print(log1)
    print(log2)
    print(log3)
    print(log4)
    print(log1,file=logfile)
    print(log2,file=logfile)
    print(log3, file=logfile)
    print(log4, file=logfile)
    logfile.close()

with tf.name_scope('Input'):
    with tf.name_scope('Input_x'):
        x = tf.placeholder(tf.float32,shape=[None,1024])
    with tf.name_scope('Input_y'):
        y_ = tf.placeholder(tf.float32,shape=[None,7])
    with tf.name_scope('Reshape_x'):
        x_image = tf.reshape(x, [-1, 32, 32, 1])
        tf.summary.image('input_reshape',x_image,max_outputs=3)
    with tf.name_scope('Drop_out_placeholder'):
        keep_prob = tf.placeholder(tf.float32)

#32*32
res_input = single_layer(input=x_image,in_channel=1,out_channel=64,conv_ksize=4,layer_name='pre_res',relu=True,trans=False)
res_input_maxpool = tf.nn.max_pool(res_input,ksize=[1,2,2,1],strides=[1,2,2,1],padding='SAME')

#16*16*64
section1 = section(input=res_input_maxpool,
                   in_channel=64,
                   out_channel1=64,
                   out_channel2=64,
                   conv_ksize=4,
                   section_name='Section_1',
                   block_num=2,
                   image_trans=False,
                   dimention_trans=False)
#16*16*64
section2 = section(input=section1,
                   in_channel=64,
                   out_channel1=128,
                   out_channel2=128,
                   conv_ksize=4,
                   section_name='Section_2',
                   block_num=2,
                   image_trans=True,
                   dimention_trans=True)
#8*8*128
section3 = section(input=section2,
                   in_channel=128,
                   out_channel1=256,
                   out_channel2=256,
                   conv_ksize=4,
                   section_name='Section_3',
                   block_num=2,
                   image_trans=True,
                   dimention_trans=True)
#4*4*256
section4 = section(input=section3,
                   in_channel=256,
                   out_channel1=512,
                   out_channel2=512,
                   conv_ksize=4,
                   section_name='Section_4',
                   block_num=1,
                   image_trans=True,
                   dimention_trans=True)

#2*2*512
avg_pool=tf.nn.max_pool(section4,ksize=[1,2,2,1],strides=[1,2,2,1],padding='SAME')

#1*1*512
with tf.variable_scope('Full_Connected_Layer1'):
    weight = tf.get_variable('weight',[avg_pool.get_shape()[3],2048],initializer=tf.contrib.layers.xavier_initializer(uniform=initializer_uniform))
    tf.add_to_collection('losses', tf.contrib.layers.l2_regularizer(L2_parameter)(weight))
    bias = tf.get_variable('bias', [2048], initializer=tf.constant_initializer(constant_initializer_parameter))
    sum_avg_flat = tf.reshape(avg_pool,[-1,int(avg_pool.get_shape()[3])])
    fc1 = tf.nn.bias_add(tf.matmul(sum_avg_flat,weight),bias)
    fc1 = leaky_relu(fc1)
    fc1 = tf.nn.dropout(fc1,keep_prob=keep_prob)
    tf.summary.histogram(' ', fc1)

with tf.variable_scope('Full_Connected_Layer2'):
    weight = tf.get_variable('weight',[fc1.get_shape()[1],1024],initializer=tf.contrib.layers.xavier_initializer(uniform=initializer_uniform))
    tf.add_to_collection('losses', tf.contrib.layers.l2_regularizer(L2_parameter)(weight))
    bias = tf.get_variable('bias', [1024], initializer=tf.constant_initializer(constant_initializer_parameter))
    fc2 = tf.nn.bias_add(tf.matmul(fc1,weight),bias)
    fc2 = leaky_relu(fc2)
    fc2 = tf.nn.dropout(fc2,keep_prob=keep_prob)
    tf.summary.histogram(' ',fc2)

with tf.variable_scope('Full_Connected_Layer3'):
    weight=tf.get_variable('weight',[fc2.get_shape()[1],7],initializer=tf.contrib.layers.xavier_initializer(uniform=initializer_uniform))
    tf.add_to_collection('losses', tf.contrib.layers.l2_regularizer(L2_parameter)(weight))
    bias=tf.get_variable('bias',[7],initializer=tf.constant_initializer(constant_initializer_parameter))
    y_conv=tf.nn.bias_add(tf.matmul(fc2,weight),bias)
    tf.summary.histogram(' ',y_conv)

with tf.name_scope('Loss'):
    cross_entropy = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=y_conv, labels=y_))
    tf.add_to_collection('losses', cross_entropy)

    loss = tf.add_n(tf.get_collection('losses'))
    tf.summary.scalar('Loss', loss)

with tf.name_scope('Train_step'):
    update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
    with tf.control_dependencies(update_ops):
        train_step = tf.train.AdamOptimizer(learning_rate).minimize(loss, global_step=global_step)

with tf.name_scope('Accuracy'):
    distribution=[tf.arg_max(y_,1),tf.arg_max(y_conv,1)]
    correct_prediction=tf.equal(distribution[0],distribution[1])

    accuracy = tf.reduce_mean(tf.cast(correct_prediction,"float"))
    tf.summary.scalar('Accuracy',accuracy)


saver=tf.train.Saver(max_to_keep=30)

merged=tf.summary.merge_all()
writer_training=tf.summary.FileWriter(checkpoint_dir+'train/',sess.graph)
writer_validation=tf.summary.FileWriter(checkpoint_dir+'validation/',sess.graph)

if Load_Data==True:
    ckpt=tf.train.get_checkpoint_state(checkpoint_dir)
    if ckpt and ckpt.model_checkpoint_path:
        saver.restore(sess,ckpt.model_checkpoint_path)
else:
    sess.run(tf.global_variables_initializer())

if Training:
    for e in range(1,1+Epoch):
        for iteration in range(iteration_time):
            batch = td.next_batch(training_batch_size)
            sess.run(train_step, feed_dict={x: batch[0], y_: batch[1], keep_prob:dropout_rate})

        training_accuracy, training_loss, result_training = sess.run([accuracy, loss, merged], feed_dict={x: batch[0], y_: batch[1], keep_prob:dropout_rate})
        validation_accuracy, validation_loss, result_validation = sess.run([accuracy, loss, merged],feed_dict={x: validation[0], y_: validation[1], keep_prob:1.0})

        log = "Epoch %d , training accuracy %g ,Validation Accuracy: %g , Loss_training : %g , Loss_validation: %g , learning rate: % g time: %s" % \
              (e, training_accuracy, validation_accuracy, training_loss, validation_loss, sess.run(learning_rate),time.ctime(time.time()))

        logfile = open(checkpoint_dir + model_name + '.txt', 'a+')
        print(log)
        print(log, file=logfile)
        logfile.close()

        writer_training.add_summary(result_training, e)
        writer_validation.add_summary(result_validation,e)
        saver.save(sess,checkpoint_dir+ model_name + '.ckpt',global_step=e)

        if Early_stop:
            if validation_accuracy > max_val_accuracy:
                max_val_accuracy = validation_accuracy
                counter=0
            else:
                counter+=1
                if counter == 30:
                    break

        if e % Test_epoch == 0:
            test_procedure()

print('final test :')
test_procedure()
sess.close()
