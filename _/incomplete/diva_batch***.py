'''
DIVergent Autoencoder (Kurtz, 2007)
- - - - - - - - - - - - - - - - - - - - - - - - - - - 

--- Functions ---
    - forward <-- get model outputs
    - loss <-- cost function
    - loss_grad <-- returns gradients
    - response <-- luce-choice rule (ie, softmax without exponentiation)
    - focusing <-- biases impact of diverse dimensions during reconstruction
    - fit <-- trains model on a number of epochs
    - predict <-- gets class predictions
    - build_params <-- returns dictionary of weights
    - update_params <-- updates weights


--- Notes ---
    - implements sum-squared-error cost function
    - hidden activation function & derivative have to be provided in 'hps' dictionary (there are some available in the utils.py script)
'''

## external requirements
import numpy as np


## "forward pass"
def forward(params, inputs, channels, hps):
    hidden_act_raw = np.add(
        np.matmul(
            inputs,
            params['input']['hidden']['weights']
        ),
        params['input']['hidden']['bias']
    )

    hidden_act = hps['hidden_activation'](hidden_act_raw)

    output_act_raw = np.array([
        np.add(
            np.matmul(
                hidden_act,
                params['hidden'][channel]['weights']
            ),
            params['hidden'][channel]['bias'],
        )
        for channel in channels
    ])

    output_act = hps['output_activation'](output_act_raw)

    return [hidden_act_raw, hidden_act, output_act_raw, output_act]


## cost function (sum squared error)
def loss(params, inputs, channel, hps, targets = None):
    if np.any(targets) == None: targets = inputs
    return np.sum(
        np.square(
            np.subtract(
                forward(params, inputs, channel, hps)[-1],
                targets
            )
        )
    ) / inputs.shape[0]


## backprop (for sum squared error cost function)
def loss_grad(params, inputs, channel, hps, targets = None):
    if np.any(targets) == None: targets = inputs

    hidden_act_raw, hidden_act, output_act_raw, output_act = forward(params, inputs, channel, hps)

    ## gradients for decode layer ( chain rule on cost function )
    decode_grad = np.multiply(
        hps['output_activation_deriv'](output_act_raw),
        (2 * (output_act - targets))  / inputs.shape[0] # <-- deriv of cost function
    )

    ## gradients for decode bias
    decode_grad_b = decode_grad.sum(axis = 0, keepdims = True)

    ## gradients for decode weights
    decode_grad_w = np.matmul(
        hidden_act.T,
        decode_grad
    )

    # - - - - - - - - - - - -

    ## gradients for encode layer ( chain rule on hidden layer )
    encode_grad = np.multiply(
        hps['hidden_activation_deriv'](hidden_act_raw),
        np.matmul(
            decode_grad, 
            params['hidden'][channel]['weights'].T
        )
    )

    ## gradients for encode weights
    encode_grad_w = np.matmul(
        inputs.T,
        encode_grad
    )

    ## gradients for encode bias
    encode_grad_b = encode_grad.sum(axis = 0, keepdims = True)

    return {
        'input': {
            'hidden': {
                'weights': encode_grad_w,
                'bias': encode_grad_b,
            }
        },
        'hidden': {
            channel: {
                'weights': decode_grad_w,
                'bias': decode_grad_b,
            }
        }
    }



## luce choice w/ late-stage attention
def response(params, inputs, channels, hps, targets = None, beta = 0):
    if np.any(targets) == None: targets = inputs

    activations = np.array([
        forward(params, inputs, channel, hps)[-1]
        for channel in channels
    ])

    # get beta weights
    fweights = np.exp(
        beta * np.mean(
            np.var(
                activations, 
                axis = 0, keepdims = True
            ),
            axis = 1
        )
    )
    fweights /= np.sum(fweights)

    channel_errors = np.sum(
        np.square(
            np.subtract(
                targets,
                activations
            )
        ) * fweights,
        axis = 2, keepdims = True
    )

    return np.divide(
        1 / channel_errors,
        np.sum(
            1 / channel_errors,
            axis = 0
        )
    )


# ## late-stage attention
# def focus(params, inputs, channels, hps, beta = 0):
#     outputs = forward(params, inputs = inputs, channels_indexed = channels_indexed, hps = hps)[-1]
    
#     fweights = np.exp(beta * np.mean(outputs.std(axis=0), axis=0))
#     fweights /= np.sum(fweights)

#     return fweights


## build parameter dictionary
def build_params(num_features, num_hidden_nodes, categories, weight_range = [-.1, .1]):
    '''
    num_features <-- (numeric) number of feature in the dataset
    num_hidden_nodes <-- (numeric)
    num_categories <-- number of category channels to make
    weight_range = [-.1,.1] <-- (list of numeric)
    '''
    return {
        'input': {
            'hidden': {
                'weights': np.random.uniform(*weight_range, [num_features, num_hidden_nodes]),
                'bias': np.random.uniform(*weight_range, [1, num_hidden_nodes]),
            }
        },
        'hidden': {
            **{
                channel: {
                    'weights': np.random.uniform(*weight_range, [num_hidden_nodes, num_features]),
                    'bias': np.random.uniform(*weight_range, [1, num_features]),
                }
                for channel in categories
            }
        }
    }


## weight update
def update_params(params, gradients, lr):
    for layer in params:
        for connection in gradients[layer]:
            params[layer][connection]['weights'] -= lr * gradients[layer][connection]['weights']
            params[layer][connection]['bias'] -= lr * gradients[layer][connection]['bias']
    return params


## fit to training set
def fit(params, inputs, labels, hps, targets = None, training_epochs = 1, randomize_presentation = True):
    if np.any(targets) == None: targets = inputs
    presentation_order = np.arange(inputs.shape[0])

    for e in range(training_epochs):
        if randomize_presentation == True: np.random.shuffle(presentation_order)
        
        for i in range(inputs.shape[0]):
            gradients = loss_grad(params, inputs[i:i+1,:], labels[i], hps, targets = targets[i:i+1,:])
            params = update_params(params, gradients, hps['learning_rate'])

    return params

## predict
def predict(params, inputs, categories, hps, targets = None):
    if np.any(targets) == None: targets = inputs
    return np.argmin(
        response(params, inputs, categories, hps, targets = targets),
        axis = 0
    )


## - - - - - - - - - - - - - - - - - -
## RUN MODEL
## - - - - - - - - - - - - - - - - - -
if __name__ == '__main__':
    # np.random.seed(0)

    inputs = np.array([
        [1, 1, 1],
        [1, 1, 0],
        [1, 0, 1],
        [1, 0, 0],

        [0, 0, 0],
        [0, 0, 1],
        [0, 1, 0],
        [0, 1, 1],
    ])

    labels = [
        'A','A','A','A', 'B','B','B','B', # <-- type 1
        # 'A','A','B','B', 'B','B','A','A', # <-- type 2
        # 'A','A','A','B', 'B','B','B','A', # <-- type 4
        # 'B','A','A','B', 'A','B','B','A', # <-- type 6
    ]

    categories = np.unique(labels)
    idx_map = {category: idx for category, idx in zip(categories, range(len(categories)))}
    labels_indexed = [idx_map[label] for label in labels]

    sigmoid = lambda x:  1 / (1 + np.exp(-x))
    sigmoid_deriv = lambda x:  sigmoid(x) * (1 - sigmoid(x))

    hps = {
        'learning_rate': .05,  # <-- learning rate
        'weight_range': [-3, 3],  # <-- weight range
        'num_hidden_nodes': 4,

        'hidden_activation': sigmoid,
        'hidden_activation_deriv': sigmoid_deriv,

        'output_activation': lambda x: x, # <-- linear output function
        'output_activation_deriv': lambda x: 1, # <-- derivative of linear output function
    }

    params = build_params(
        inputs.shape[1],  # <-- num features
        hps['num_hidden_nodes'],
        categories,
        weight_range = hps['weight_range']
    )

    num_training_epochs = 100
    params = fit(params, inputs, labels, hps, targets = inputs / 2 + .5, training_epochs = num_training_epochs)
    p = predict(params, inputs, categories, hps, targets = inputs / 2 + .5)
    print(p)

