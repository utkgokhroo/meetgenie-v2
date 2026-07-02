import cv2
import numpy as np
import mss
import time

recording = False


def record_screen(output_file="recording.mp4", fps=15):

    global recording

    recording = True

    screen = mss.mss()
    monitor = screen.monitors[1]

    width = monitor["width"]
    height = monitor["height"]

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    out = cv2.VideoWriter(
        output_file,
        fourcc,
        fps,
        (width, height)
    )

    print("Screen recording started...")

    frame_time = 1 / fps

    while recording:

        start = time.perf_counter()

        img = np.array(screen.grab(monitor))

        frame = cv2.cvtColor(
            img,
            cv2.COLOR_BGRA2BGR
        )

        out.write(frame)

        elapsed = time.perf_counter() - start

        if elapsed < frame_time:
            time.sleep(frame_time - elapsed)

    out.release()

    print("Screen recording stopped")


def stop_screen():

    global recording

    recording = False