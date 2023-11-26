from absl import flags

FLAGS = flags.FLAGS


class Main:
    def __init__(self):
        print("main test")
        print(FLAGS.agent.test.a)
