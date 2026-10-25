import numpy as np
class BudgetExpired(Exception):
    pass


def states_and_jacobian(theta, edges, n, columns, zset):
    """Forward state and tangent propagation, independent of Cirq compilation."""
    all_states = np.zeros((len(theta) + 1, columns, 2**n))
    for r in range(columns):
        all_states[0, r, (1 << r) - 1] = 1
    gates = [('ry', q) for q in range(n)]
    for a, b in edges:
        gates.extend([('cz', (a, b)), ('ry', a), ('ry', b)])
    parameter = 0
    indices = np.arange(2**n)
    for kind, data in gates:
        if kind == 'cz':
            a, b = data
            mask = (1 << (n - 1 - a)) | (1 << (n - 1 - b))
            all_states[:, :, (indices & mask) == mask] *= -1
            continue
        tensor = all_states.reshape((len(theta) + 1, columns) + (2,) * n)
        a, b = np.take(tensor, 0, axis=data + 2), np.take(tensor, 1, axis=data + 2)
        co, si = np.cos(theta[parameter] / 2), np.sin(theta[parameter] / 2)
        tensor = np.stack([co * a - si * b, si * a + co * b], axis=data + 2)
        state = tensor[0]
        a, b = np.take(state, 0, axis=data + 1), np.take(state, 1, axis=data + 1)
        tensor[parameter + 1] = np.stack([-b / 2, a / 2], axis=data + 1)
        all_states = tensor.reshape((len(theta) + 1, columns, 2**n))
        parameter += 1
    assert parameter == len(theta)
    for q in zset:
        all_states[:, :, (indices & (1 << (n-1-q))) != 0] *= -1
    return all_states[0], all_states[1:].reshape(len(theta), -1).T

