"""Hold-to-drive manual controls in body coordinates: forward, right, up."""
KEY_AXES = {'w': (0, 1), 'up': (0, 1), 's': (0, -1), 'down': (0, -1),
            'd': (1, 1), 'right': (1, 1), 'a': (1, -1), 'left': (1, -1),
            'r': (2, 1), 'f': (2, -1)}


def mix(surge, yaw, heave):
    port, starboard = surge + yaw, surge - yaw
    scale = max(1.0, abs(port), abs(starboard))
    return [port / scale, starboard / scale, max(-1., min(1., heave))]


class ManualControls:
    def __init__(self, power=.6):
        self.power = power
        self.held = set()
        self.blocked = set()

    def press(self, key):
        if key in KEY_AXES and key not in self.blocked:
            self.held.add(key)

    def release(self, key):
        self.held.discard(key)
        self.blocked.discard(key)

    def stop(self):
        # OS key repeat must not re-arm a key that was held at emergency stop.
        self.blocked.update(self.held)
        self.held.clear()

    def command(self):
        axes = [0., 0., 0.]
        for axis in range(3):
            signs = {KEY_AXES[k][1] for k in self.held if KEY_AXES[k][0] == axis}
            axes[axis] = sum(signs) * self.power
        return mix(*axes)
