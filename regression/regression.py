# This is an example of fitting a model to data gathered using pset
#
# The general workflow I've used for trying to model contention is simply:
#
# 1. Write a script using pset to gather samples of program runtime characteristics,
#		capturing features of their runtimes when run alone and their slowdown with contention
#
# 2. Output each sample to a csv
#
# 3. Use a similar script as this one to train a model on that data to predict slowdown
#		of two contending programs
#


import pandas as pd
from sklearn.svm import SVR
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import numpy as np

# read in a CSV file of the data
#df = pd.read_csv('l3andbuscontention.csv')
#df = pd.read_csv('l3andbuscontention-withCAT.csv')
df = pd.read_csv('l3contention.csv')

# input features
X = df[['delayX', 'delayY']]	# 'delay' is an artificial feature of the synthetic program
															# I've been using. A more practical feature would be
															# working set size and/or memory bus demand

# output feature
y = df.slowdownX


# prepare a few models
svr_linear = make_pipeline(StandardScaler(), SVR(kernel='linear'))
svr_rbf = make_pipeline(StandardScaler(), SVR(kernel='rbf'))
ridge = make_pipeline(StandardScaler(), Ridge(solver='auto'))
forest = make_pipeline(StandardScaler(), RandomForestRegressor(n_estimators=10))

# fit the given model and test it on a sample
# print the results
def run(model, X, y):
	X_train, X_test, y_train, y_test = train_test_split(X,y,random_state=0)
	
	model.fit(X_train,y_train)

	y_pred = model.predict(X_test)
	mse = mean_squared_error(y_test, y_pred)
	rmse = np.sqrt(mse)
	print("MSE", mse)
	print("RMSE", rmse)

	results = X_test.assign(predicted=y_pred, actual=y_test)
	print(results)
	

#print("with SVR linear:")
#run(svr_linear, X, y)

print("with SVR rbf:")
run(svr_rbf, X, y)

#print("with forest:")
#run(forest, X, y)

