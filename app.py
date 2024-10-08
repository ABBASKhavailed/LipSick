import subprocess
import gradio as gr
import os
import warnings
from compute_crop_radius import calculate_crop_radius_statistics
from utils.reference_frame import extract_and_crop_frame, delete_existing_reference_frames, overlay_text
import cv2

# Suppress specific warnings about video conversion
warnings.filterwarnings("ignore", message="Video does not have browser-compatible container or codec. Converting to mp4")

def get_versioned_filename(filepath):
    base, ext = os.path.splitext(filepath)
    counter = 1
    versioned_filepath = filepath
    while os.path.exists(versioned_filepath):
        versioned_filepath = f"{base}({counter}){ext}"
        counter += 1
    return versioned_filepath

def compute_crop_radius_stats(video_file):
    if video_file is None:
        return "Please upload a video file first."
    print("Computing Crop Radius...")
    _, _, _, most_common = calculate_crop_radius_statistics(video_file.name)
    print(f"Done: Crop radius = {most_common}")
    return most_common

def process_files(source_video, driving_audio, custom_crop_radius=None, auto_mask=True, ref_index_1=None, ref_index_2=None, ref_index_3=None, ref_index_4=None, ref_index_5=None, activate_custom_frames=False):
    ref_indices = [index for index in [ref_index_1, ref_index_2, ref_index_3, ref_index_4, ref_index_5] if index is not None]
    if custom_crop_radius is None or custom_crop_radius == 0:
        ref_indices = [index + 5 for index in ref_indices]
    ref_indices_str = ','.join(map(str, ref_indices)) if len(ref_indices) == 5 else ""

    if not driving_audio:
        print("Please upload audio first.")
        return "", "Error: Audio file is required."

    pretrained_model_path = "./asserts/pretrained_lipsick.pth"
    deepspeech_model_path = "./asserts/output_graph.pb"
    res_video_dir = "./asserts/inference_result"

    base_name = os.path.splitext(os.path.basename(source_video))[0]
    output_video_name = f"{base_name}_lipsick.mp4" if not auto_mask else "LipSick_Blend.mp4"
    output_video_path = os.path.join(res_video_dir, output_video_name)
    output_video_path = get_versioned_filename(output_video_path)

    cmd = [
        'python', 'inference.py',
        '--source_video_path', source_video,
        '--driving_audio_path', driving_audio,
        '--pretrained_lipsick_path', pretrained_model_path,
        '--deepspeech_model_path', deepspeech_model_path,
        '--res_video_dir', res_video_dir,
        '--custom_reference_frames', ref_indices_str
    ]

    if custom_crop_radius is not None:
        cmd.extend(['--custom_crop_radius', str(custom_crop_radius)])

    if activate_custom_frames:
        cmd.append('--activate_custom_frames')

    if auto_mask:
        cmd.append('--auto_mask')

    try:
        subprocess.run(cmd, check=True)
        print("Complete")
        print("Result saved in ./asserts/inference_results")
        print("Thank you for using LipSick for your Lip-Sync needs.")
        
        # Return the path of the processed video
        return "", output_video_path
        
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        return "An error occurred during processing. Please check the console log.", ""

def visualize_reference_frames(video_path, ref_index_1, ref_index_2, ref_index_3, ref_index_4, ref_index_5):
    delete_existing_reference_frames()  # Delete existing reference frames before visualization
    ref_indices = [ref_index_1, ref_index_2, ref_index_3, ref_index_4, ref_index_5]
    frames = []
    for index in ref_indices:
        if index is not None:
            frame_path = extract_and_crop_frame(video_path, int(index), crop_to_face=False)  # Don't crop to face
            frame = cv2.imread(frame_path)
            frame_with_text = overlay_text(frame, int(index), face_detected=True)  # Assume face detected
            cv2.imwrite(frame_path, frame_with_text)  # Save the frame with text overlay
            frames.append(frame_path)
    return frames

with gr.Blocks(css=".input_number { width: 80px; }") as iface:
    gr.Markdown("### 🤢 LIPSICK 🤮\nUpload your video and driving audio to Lipsync.")

    with gr.Tab("Process Video"):
        source_video = gr.File(label="Upload MP4 File", type="filepath", file_types=["mp4"])
        driving_audio = gr.File(label="Upload .Wav Audio File", type="filepath", file_types=["wav"])
        
        with gr.Accordion("Advanced Options", open=False):
            auto_mask = gr.Checkbox(label="Auto Mask", value=True)
            face_tracker_options = ['dlib', 'opencv', 'openface', 'sfd', 'blazeface']
            face_tracker = gr.CheckboxGroup(
                label="Face Tracker",
                choices=face_tracker_options,
                value=['dlib'],
                type="index",
                interactive=False
            )
            gr.Markdown("___")  # Visual separator for layout
            
            activate_custom_frames = gr.Checkbox(label="Activate Custom Reference Frames", value=False)
            
            gr.Markdown("""
            Enter custom reference frames for example 0 1 2 3 4 5. 
            All boxes must be filled with a value and the checkbox above must be activated. 
            You can use the same frame more than once, for example 9 9 8 9 1 or 1 1 1 1 1. 
            If you leave any box empty, even if the checkbox is activated, it will revert to using random reference frames for all 5 boxes. 
            Don't be worried if you print these values and a value of 5 has been added to each in some circumstances, as in that case they will have 5 subtracted from each value at the correct part of the code. 
            I will make this UI better that will allow visualization of custom frames, etc., at a later date. 
            I prefer to use one reference frame for all 5 frames and ensure that frame is showing teeth.
""")

            with gr.Row():
                ref_index_1 = gr.Number(label="Frame")
                ref_index_2 = gr.Number(label="Frame")
                ref_index_3 = gr.Number(label="Frame")
                ref_index_4 = gr.Number(label="Frame")
                ref_index_5 = gr.Number(label="Frame")

            visualize_btn = gr.Button("Visualize Reference Frames")
            reference_images = gr.Gallery(label="Reference Frames", elem_id="reference_frames")

            visualize_btn.click(
                fn=visualize_reference_frames,
                inputs=[source_video, ref_index_1, ref_index_2, ref_index_3, ref_index_4, ref_index_5],
                outputs=[reference_images]
            )

            gr.Markdown("___")
            compute_crop_btn = gr.Button("Compute Crop Radius Stats")
            compute_crop_btn.click(
                fn=compute_crop_radius_stats,
                inputs=[source_video],
                outputs=[]
            )

            custom_crop_radius = gr.Number(label="Custom Crop Radius (Optional)", value=None)
            gr.Markdown("Specify a custom crop radius for video processing if required.")

        gr.Markdown("___")  # Visual spacer

        process_btn = gr.Button("Process Video")
        output_video = gr.Video(label="Processed Video", show_label=False)
        status_text = gr.Textbox(visible=False)  # Reintroduce a hidden Textbox for stability
        # Adjust outputs to include only the processed video
        process_btn.click(
            fn=process_files,
            inputs=[source_video, driving_audio, custom_crop_radius, auto_mask, ref_index_1, ref_index_2, ref_index_3, ref_index_4, ref_index_5, activate_custom_frames],
            outputs=[status_text, output_video]
        )
    iface.launch(share=True)
