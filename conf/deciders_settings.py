
from __future__ import division

# Confidence level for classifying 
TRESHOLD = 0.85

# Calculate precision of a combination of parameters
def PRECISION(true_pos, false_pos, true_neg, false_neg):
    if true_pos + false_pos > 0:
        return true_pos / (true_pos + false_pos)
    return 0


# For NeuronDecider
HIDDEN_NEURONS = 1

