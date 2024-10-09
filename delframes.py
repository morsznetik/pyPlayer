import os


def delete_and_rename_frames(frames_path):
    frames = sorted(os.listdir(frames_path))

    # Delete every 2nd frame
    for i in range(1, len(frames), 2):
        frame_to_delete = os.path.join(frames_path, frames[i])
        os.remove(frame_to_delete)

    # Rename the remaining frames
    for i, old_name in enumerate(sorted(os.listdir(frames_path))):
        new_name = os.path.join(frames_path, f"frame_{i:04d}.png")
        os.rename(os.path.join(frames_path, old_name), new_name)


if __name__ == "__main__":
    frames_output_path = "output/frames"

    # Assuming frames are already extracted, run this function after splitting the video
    delete_and_rename_frames(frames_output_path)
