
import numpy as np
from hmmlearn import hmm
import hmmlearn

print(f"hmmlearn version: {hmmlearn.__version__}")

model = hmm.GaussianHMM(n_components=2, n_iter=10)
X = np.random.randn(100, 1)
model.fit(X)

X_test = np.random.randn(1, 1)
ret = model.score_samples(X_test)
print(f"score_samples return type: {type(ret)}")
print(f"score_samples return value: {ret}")
