"""
Utilities for compatibility for other libraries such as scikit-learn.
"""
import copy

import numpy as np
try:
    import pandas as pd
    PANDAS_INSTALLED = True
except ImportError:
    PANDAS_INSTALLED = False
from sklearn import base as sklearn_base
from sklearn import preprocessing
from sklearn import utils

from . import base
from . import compose
from . import stream


STREAM_METHODS = {
    np.ndarray: stream.iter_numpy
}

if PANDAS_INSTALLED:
    STREAM_METHODS[pd.DataFrame] = stream.iter_pandas

# Params passed to sklearn.utils.check_X_y and sklearn.utils.check_array
SKLEARN_INPUT_X_PARAMS = {
    'accept_sparse': False,
    'accept_large_sparse': True,
    'dtype': 'numeric',
    'order': None,
    'copy': False,
    'force_all_finite': True,
    'ensure_2d': True,
    'allow_nd': False,
    'ensure_min_samples': 1,
    'ensure_min_features': 1,
    'warn_on_dtype': False
}

# Params passed to sklearn.utils.check_X_y in addition to SKLEARN_INPUT_X_PARAMS
SKLEARN_INPUT_Y_PARAMS = {
    'multi_output': False,
    'y_numeric': False
}


class SKLBaseWrapper(sklearn_base.BaseEstimator):
    """This class exists for adapting the documentation styling."""

    def __init__(self, creme_estimator):
        self.creme_estimator = creme_estimator

    def get_params(self, deep=True):
        """Get parameters for this estimator.

        Parameters:
            deep (bool, optional) If True, will return the parameters for this estimator and
            contained subobjects that are estimators.

        Returns:
            dict of string to any: Parameter names mapped to their values.

        """
        return super().get_params(deep=deep)

    def set_params(self, **params):
        """Set the parameters of this estimator.

        The method works on simple estimators as well as on nested objects (such as pipelines). The
        latter have parameters of the form ``<component>__<parameter>`` so that it's possible to
        update each component of a nested object.

        Returns:
            self

        """
        return super().set_params(**params)


class SKLRegressorWrapper(SKLBaseWrapper, sklearn_base.RegressorMixin):

    def fit(self, X, y):
        """Fits to an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))
            y (array-like of shape n_samples)

        Returns:
            self

        """
        # Check the estimator is a Regressor
        if isinstance(self.creme_estimator, compose.Pipeline):
            if not isinstance(self.creme_estimator._final_estimator, base.Regressor):
                raise ValueError('creme_estimator is not a Regressor')
        elif not isinstance(self.creme_estimator, base.Regressor):
            raise ValueError('creme_estimator is not a Regressor')

        # Check the inputs
        X, y = utils.check_X_y(X, y, **SKLEARN_INPUT_X_PARAMS, **SKLEARN_INPUT_Y_PARAMS)

        # scikit-learn's convention is that fit shouldn't mutate the input parameters; we have to
        # deep copy the provided estimator in order to respect this convention
        self.instance_ = copy.deepcopy(self.creme_estimator)

        # Call fit_one for each observation
        for x, yi in STREAM_METHODS[type(X)](X, y):
            self.instance_.fit_one(x, yi)

        # predict needs some way to know if fit has been called
        self.is_fitted_ = True

        return self

    def predict(self, X):
        """Predicts the target of an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))

        Returns:
            array of shape (n_samples,): Predicted target values for each row of ``X``.

        """
        # Check the fit method has been called
        utils.validation.check_is_fitted(self, 'is_fitted_')

        # Check the input
        X = utils.check_array(X, **SKLEARN_INPUT_X_PARAMS)

        # Make a prediction for each observation
        y_pred = np.empty(shape=len(X))
        for i, (x, _) in enumerate(stream.iter_numpy(X)):
            y_pred[i] = self.instance_.predict_one(x)

        return y_pred

    def score(self, X, y, sample_weight=None):
        """Returns the coefficient of determination R^2 of the prediction.

        The coefficient R^2 is defined as (1 - u/v), where u is the residual sum of squares
        ((y_true - y_pred) ** 2).sum() and v is the total sum of squares
        ((y_true - y_true.mean()) ** 2).sum(). The best possible score is 1.0 and it can be
        negative (because the model can be arbitrarily worse). A constant model that always
        predicts the expected value of y, disregarding the input features, would get a R^2 score of
        0.0.

        Parameters:

            X (array-like of shape (n_samples, n_features)): Test samples.
            y (array-like of shape = (n_samples) or (n_samples, n_outputs): True values for X.
            sample_weight (array-like of shape = [n_samples], optional): Sample weights.

        Returns:
            float: R^2 of self.predict(X) w.r.t. y.

        """
        return super().score(X, y, sample_weight)

    def fit_predict(self, X, y):
        """Calls ``fit`` and then ``predict`` in one go."""
        return self.fit(X, y).predict(X)


class SKLClassifierWrapper(SKLBaseWrapper, sklearn_base.ClassifierMixin):

    @property
    def is_binary(self):
        if isinstance(self.creme_estimator, compose.Pipeline):
            return isinstance(self.creme_estimator._final_estimator, base.BinaryClassifier)
        return isinstance(self.creme_estimator, base.BinaryClassifier)

    def fit(self, X, y):
        """Fits to an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))
            y (array-like of shape n_samples)

        Returns:
            self

        """
        # Check the estimator is either a BinaryClassifier or a MultiClassifier
        if isinstance(self.creme_estimator, compose.Pipeline):
            if not isinstance(
                self.creme_estimator._final_estimator,
                (base.BinaryClassifier, base.MultiClassifier)
            ):
                raise ValueError('creme_estimator is not a BinaryClassifier nor a MultiClassifier')
        elif not isinstance(self.creme_estimator, (base.BinaryClassifier, base.MultiClassifier)):
            raise ValueError('creme_estimator is not a BinaryClassifier nor a MultiClassifier')

        # Check the inputs
        X, y = utils.check_X_y(X, y, **SKLEARN_INPUT_X_PARAMS, **SKLEARN_INPUT_Y_PARAMS)

        # Check the number of classes agrees with the type of classifier
        self.classes_ = np.unique(y)
        if len(self.classes_) > 2 and self.is_binary:
            raise ValueError('n_classes is more than 2 but creme_estimator is a BinaryClassifier')
        if len(self.classes_) < 3 and not self.is_binary:
            raise ValueError('n_classes is less than 3 but creme_estimator is a MultiClassifier')

        # creme's BinaryClassifier expects bools or 0/1 values
        if self.is_binary:
            self.label_encoder_ = preprocessing.LabelEncoder().fit(y)
            y = self.label_encoder_.transform(y)

        # scikit-learn's convention is that fit shouldn't mutate the input parameters; we have to
        # deep copy the provided estimator in order to respect this convention
        self.instance_ = copy.deepcopy(self.creme_estimator)

        # Call fit_one for each observation
        for x, yi in STREAM_METHODS[type(X)](X, y):
            self.instance_.fit_one(x, yi)

        return self

    def predict_proba(self, X):
        """Predicts the target probability of an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))

        Returns:
            array of shape (n_samples,): Predicted target values for each row of ``X``.

        """
        # Check the fit method has been called
        utils.validation.check_is_fitted(self, 'classes_')

        # Check the input
        X = utils.check_array(X, **SKLEARN_INPUT_X_PARAMS)

        # creme's predictions have to converted to follow the scikit-learn conventions
        if self.is_binary:
            def extract_proba(y_pred):
                return [1 - y_pred, y_pred]
        else:
            def extract_proba(y_pred):
                return [y_pred.get(c, 0) for c in self.classes_]

        # Make a prediction for each observation
        y_pred = np.empty(shape=(len(X), len(self.classes_)))
        for i, (x, _) in enumerate(stream.iter_numpy(X)):
            y_pred[i] = extract_proba(self.instance_.predict_proba_one(x))

        return y_pred

    def predict(self, X):
        """Predicts the target of an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))

        Returns:
            array of shape (n_samples,): Predicted target values for each row of ``X``.

        """
        # Check the fit method has been called
        utils.validation.check_is_fitted(self, 'classes_')

        # Check the input
        X = utils.check_array(X, **SKLEARN_INPUT_X_PARAMS)

        # Make a prediction for each observation
        y_pred = np.empty(shape=len(X))
        for i, (x, _) in enumerate(stream.iter_numpy(X)):
            y_pred[i] = self.instance_.predict_one(x)

        return y_pred

    def score(self, X, y, sample_weight=None):
        """Returns the mean accuracy on the given test data and labels.
        In multi-label classification, this is the subset accuracy
        which is a harsh metric since you require for each sample that
        each label set be correctly predicted.

        Parameters:

            X (array-like of shape (n_samples, n_features)): Test samples.
            y (array-like of shape = (n_samples) or (n_samples, n_outputs): True values for X.

        Returns:
            float: Mean accuracy of self.predict(X) w.r.t. y.

        """
        return super().score(X, y, sample_weight)

    def fit_predict(self, X, y):
        """Calls ``fit`` and then ``predict`` in one go."""
        return self.fit(X, y).predict(X)


class SKLTransformerWrapper(SKLBaseWrapper, sklearn_base.TransformerMixin):

    def fit(self, X, y=None):
        """Fits to an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))
            y (array-like of shape n_samples)

        Returns:
            self

        """
        # Check the estimator is a Transformer
        if isinstance(self.creme_estimator, compose.Pipeline):
            if not isinstance(self.creme_estimator._final_estimator, base.Transformer):
                raise ValueError('creme_estimator is not a Transformer')
        elif not isinstance(self.creme_estimator, base.Transformer):
            raise ValueError('creme_estimator is not a Transformer')

        # Check the inputs
        if y is None:
            X = utils.check_array(X, **SKLEARN_INPUT_X_PARAMS)
        else:
            X, y = utils.check_X_y(X, y, **SKLEARN_INPUT_X_PARAMS, **SKLEARN_INPUT_Y_PARAMS)

        # scikit-learn's convention is that fit shouldn't mutate the input parameters; we have to
        # deep copy the provided estimator in order to respect this convention
        self.instance_ = copy.deepcopy(self.creme_estimator)

        # Call fit_one for each observation
        for x, yi in STREAM_METHODS[type(X)](X, y):
            self.instance_.fit_one(x, yi)

        # predict needs some way to know if fit has been called
        self.is_fitted_ = True

        return self

    def transform(self, X):
        """Predicts the target of an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))

        Returns:
            array: Transformed output.

        """
        # Check the fit method has been called
        utils.validation.check_is_fitted(self, 'is_fitted_')

        # Check the input
        X = utils.check_array(X, **SKLEARN_INPUT_X_PARAMS)

        # Call predict_proba_one for each observation
        X_trans = [None] * len(X)
        for i, (x, _) in enumerate(stream.iter_numpy(X)):
            X_trans[i] = list(self.instance_.transform_one(x).values())

        return np.asarray(X_trans)

    def fit_transform(self, X, y=None):
        """Calls ``fit`` and then ``transform`` in one go."""
        return self.fit(X, y).transform(X)


class SKLClustererWrapper(SKLBaseWrapper, sklearn_base.ClusterMixin):

    def fit(self, X, y=None):
        """Fits to an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))
            y (array-like of shape n_samples)

        Returns:
            self

        """
        # Check the estimator is a Clusterer
        if not isinstance(self.creme_estimator, base.Clusterer):
            raise ValueError('creme_estimator is not a Clusterer')

        # Check the inputs
        X = utils.check_array(X, **SKLEARN_INPUT_X_PARAMS)

        # scikit-learn's convention is that fit shouldn't mutate the input parameters; we have to
        # deep copy the provided estimator in order to respect this convention
        self.instance_ = copy.deepcopy(self.creme_estimator)

        # Call fit_one for each observation
        self.labels_ = np.empty(len(X), dtype=np.int32)
        for i, (x, yi) in enumerate(STREAM_METHODS[type(X)](X, y)):
            label = self.instance_.fit_one(x, yi)
            self.labels_[i] = label

        # predict needs some way to know if fit has been called
        self.is_fitted_ = True

        return self

    def predict(self, X):
        """Predicts the target of an entire dataset contained in memory.

        Parameters:
            X (array-like of shape (n_samples, n_features))

        Returns:
            array: Transformed output.

        """
        # Check the fit method has been called
        utils.validation.check_is_fitted(self, 'is_fitted_')

        # Check the input
        X = utils.check_array(X, **SKLEARN_INPUT_X_PARAMS)

        # Call predict_proba_one for each observation
        y_pred = np.empty(len(X), dtype=np.int32)
        for i, (x, _) in enumerate(stream.iter_numpy(X)):
            y_pred[i] = self.instance_.predict_one(x)

        return y_pred

    def fit_predict(self, X, y=None):
        """Calls ``fit`` and then ``predict`` in one go."""
        return self.fit(X, y).predict(X)
