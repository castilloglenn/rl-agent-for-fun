"""A game's worker process (roadmap 8, decision 073): plays one game for
a training, answering its messages until the pipe closes.

    python -m src.experiments.game_worker

Messages come pickled on stdin and answers go pickled on stdout, each as
(kind, value): ("ok", answer) or ("error", traceback). Anything printed
goes to stderr instead, so it can't break the pipe's format. Ctrl+C is
for the training process: the worker ignores it and ends when the
training does (its stdin closes).
"""

import os
import pickle
import signal
import sys
import traceback


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    answers = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())  # prints: stderr
    messages = sys.stdin.buffer
    from src.experiments.games import Game

    game = None
    while True:
        try:
            message = pickle.load(messages)
        except EOFError:
            return  # the training ended
        try:
            if message[0] == "setup":
                game, answer = Game(message[1]), None
            else:
                answer = game.handle(message)
            reply = ("ok", answer)
        except Exception:  # noqa: BLE001 - every failure goes back
            reply = ("error", traceback.format_exc())
        pickle.dump(reply, answers, pickle.HIGHEST_PROTOCOL)
        answers.flush()
        if message[0] == "close":
            return


if __name__ == "__main__":
    main()
