**Version 0.0.2**

- Cleaned the documentation (still work to do though)
- Added passive-aggressive models to the `linear_model` module
- Added `HedgeClassifier` to the `ensemble` module
- Added `RandomDiscarder` to the `feature_selection` module
- Added `NUnique`, `Min`, `Max`, `PeakToPeak`, `Kurtosis`, `Skew`, `Sum`, `EWMean` to the `stats` module
- Made sure the running statistics produce the same results as `pandas`'s `rolling` method
- Added `AbsoluteLoss`, `HingeLoss`, `EpsilonInsensitiveHingeLoss` to the `optim` module
- Added scikit-learn wrappers to the `compat` module
- Added `TargetEncoder` to the `feature_extraction` module
