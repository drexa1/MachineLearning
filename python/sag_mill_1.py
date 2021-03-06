import logging
import os
import timeit
import keras
import numpy as np
from keras import layers
from keras.models import Sequential
from keras.optimizers import RMSprop
from matplotlib import pyplot as plt
from pandas import read_csv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

os.environ['TF_CPP_MIN_LOG_LEVEL']='2'

def main():
	logger.info("Loading dataset...")
	float_data = get_data('sag_mill.csv')

	target1 = float_data['Mill main drive - Main motor current'].values
	f1 = plt.figure(1)
	plt.plot(range(len(target1)), target1, 'b', label='Mill main drive - Main motor current')
	f1.show()
	target2 = float_data['Mill weight'].values
	f2 = plt.figure(2)
	plt.plot(range(len(target2)), target2, 'g', label='Mill weight')
	f2.show()

	logger.info("Normalizing...")
	data = normalize(float_data)

	lookback = 60*24
	step = 1
	delay = 10
	batch_size = 128

	train_gen = generator(data, lookback=lookback, delay=delay, min_index=None, max_index=300000, step=step, batch_size=batch_size)
	val_gen = generator(data, lookback=lookback, delay=delay, min_index=300001, max_index=400000, step=step, batch_size=batch_size)
	test_gen = generator(data, lookback=lookback, delay=delay, min_index=400001, max_index=None, step=step, batch_size=batch_size)

	logger.info("Creating model...")
	model = Sequential()
	model.add(layers.LSTM(32, dropout=0.1, recurrent_dropout=0.5, return_sequences=True, input_shape=(None, data.shape[-1])))
	model.add(layers.LSTM(64, activation='relu', dropout=0.1, recurrent_dropout=0.5))
	model.add(layers.Dense(2))

	logger.info("Compiling model...")
	model.compile(optimizer=RMSprop(), loss='mae')

	val_steps = (400000 - 300001 - lookback) // batch_size
	start = timeit.timeit()
	history = model.fit_generator(train_gen, steps_per_epoch=500, epochs=50, validation_data=val_gen, validation_steps=val_steps, callbacks=model_callbacks())
	end = timeit.timeit()
	logger.info("Training took: %s", end - start)

	loss = history.history['loss']
	val_loss = history.history['val_loss']
	epochs = range(1, len(loss) + 1)

	plt.figure()
	plt.plot(epochs, loss, 'b', label='Training loss')
	plt.plot(epochs, val_loss, 'g', label='Validation loss')
	plt.show()

	logger.info("Done")

def model_callbacks():
	keras.callbacks.ModelCheckpoint(filepath='sag_mill_0.h5', monitor='val_loss', save_best_only=True,)
	earlystop_callback = keras.callbacks.EarlyStopping(monitor='acc', patience=1)
	plateau_callback = keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.1, patience=10)
	tensorboard_callback = keras.callbacks.TensorBoard(log_dir='sag_mill_0')
	return [earlystop_callback, plateau_callback, tensorboard_callback]

def get_data(csv_file):
	df = read_csv(csv_file, na_values=[''])
	df.drop(['time'], 1, inplace=True)
	df.dropna(inplace=True)
	logger.info("Checking for NaN's...")
	logger.debug(df.isnull().any())
	return df

def normalize(data):
	mean = data.mean(axis=0)
	data -= mean
	std = data.std(axis=0)
	data /= std
	return data

def generator(data, lookback, delay, min_index, max_index, shuffle=False, batch_size=128, step=1):
	if min_index is None:
		min_index = 0
	if max_index is None:
		max_index = len(data) - delay - 1
	index = min_index + lookback
	while True:
		if shuffle:
			rows = np.random.randint(min_index + lookback, max_index, size=batch_size)
		else:
			if index + batch_size >= max_index:
				index = min_index + lookback
			rows = np.arange(index, min(index + batch_size, max_index))
			index += len(rows)

		x = np.zeros((len(rows), lookback//step, data.shape[1]))
		y = np.zeros((len(rows), 2))
		for i, row in enumerate(rows):
			indices = range(rows[i] - lookback, rows[i], step)
			x[i] = data.values[indices]
			target1_col = data.columns.get_loc('Mill main drive - Main motor current')
			y[i,0] = data.values[rows[i] + delay][target1_col]
			target2_col = data.columns.get_loc('Mill weight')
			y[i,1] = data.values[rows[i] + delay][target2_col]

		yield x, y

if __name__ == "__main__":
	# execute only if run as a script
	main()
