# ZED Stereo Depth Measurement Tool

## Short Description

A ZED SDK stereo-depth measurement tool that synchronizes RGB and depth views, filters unreliable depth, samples local 3D point-cloud neighborhoods, and computes centimeter-scale distances between selected points. Designed for calibrated underwater and field measurement workflows.

## Demo Videos

### Small Pipes Measurement

True measurements:

- Small pipe: `15 cm`
- Long pipe: `40 cm`

<p align="center">
  <a href="https://www.youtube.com/watch?v=FpWF3fpKW68">
      <img src="https://github.com/user-attachments/assets/eb4f9c3a-f506-442e-ac75-42766106cefc" alt="Target Measurement Demo" width="800">

  </a>
</p>

<p align="center">
  <a href="https://www.youtube.com/watch?v=0gPI-CR7d_U">
    <strong>Watch Small Pipes Measurement Demo</strong>
  </a>
</p>

---

### Target Measurement

True measurement:

- Target length: `10 cm`

<p align="center">
  <a href="https://www.youtube.com/watch?v=FpWF3fpKW68">
    <img src="https://github.com/user-attachments/assets/01c80a62-1eb6-4551-967f-f97a8515270e" alt="Small Pipes Measurement Demo" width="800">
  </a>
</p>

<p align="center">
  <a href="https://www.youtube.com/watch?v=0gPI-CR7d_U">
    <strong>Watch Target Measurement Demo</strong>
  </a>
</p>

## Overview

This project is an interactive stereo-depth distance measurement tool built with the ZED SDK, Python, and OpenCV. It uses the ZED camera’s stereo depth pipeline to recover 3D coordinates from selected image points, then computes the real-world Euclidean distance between two selected points.

The system displays a dual-panel interface:

- Left panel: high-resolution RGB image.
- Right panel: live depth visualization.

The operator can click on either the RGB panel or the depth panel. For each selected point, the system retrieves the corresponding 3D coordinate from the ZED point cloud. Once two valid points are selected, the tool calculates the real-world distance between them and displays the result in centimeters.

The tool was designed for practical measurement workflows where visual confirmation and depth reliability are both important, especially in underwater, robotic, and field-inspection environments.

## Purpose

The main purpose of this project is to improve real-world distance measurement using ZED stereo depth data by combining:

- RGB-based visual target identification.
- Depth-map validation.
- ZED SDK confidence filtering.
- Local point-cloud sampling around the selected pixel.
- Robust spatial filtering to reduce noisy single-pixel depth values.
- Euclidean 3D distance calculation.

This makes the system more reliable than measuring from a single raw depth pixel.

## Measurement Pipeline

The depth measurement pipeline is built around a synchronized dual-panel interface that combines high-fidelity RGB imagery with live spatial depth maps. The operator identifies the target feature visually, while the system resolves its 3D position through stereo disparity and point-cloud reconstruction.

The pipeline follows these main steps:

1. The ZED camera captures synchronized stereo frames.
2. The ZED SDK computes a depth map using the selected depth mode.
3. The system retrieves the left RGB image, depth visualization, and XYZ point cloud.
4. The operator selects two points on either the RGB panel or depth panel.
5. For each clicked point, the system samples a local region around the pixel.
6. Invalid, non-finite, and unreliable depth samples are rejected.
7. A local median or window-based spatial estimate is computed from the valid 3D samples.
8. The 3D Euclidean distance between the two selected points is calculated.
9. The result is converted from meters to centimeters and displayed on screen.

The final distance is computed as:

```text
distance_cm = ||P2 - P1|| × 100
```

Where:

```text
P1 = (X1, Y1, Z1)
P2 = (X2, Y2, Z2)
```

The ZED SDK provides the 3D point-cloud coordinates in meters, and the program converts the final result to centimeters.

## ZED SDK Optimization Strategy

This project improves measurement stability by tuning ZED SDK parameters and avoiding direct reliance on a single depth pixel.

### 1. Depth Mode Selection

The ZED SDK provides different depth modes that trade off speed, density, accuracy, and computational cost.

Common depth modes include:

```python
sl.DEPTH_MODE.PERFORMANCE
sl.DEPTH_MODE.ULTRA
sl.DEPTH_MODE.NEURAL
sl.DEPTH_MODE.NEURAL_PLUS
```

The uploaded implementation uses:

```python
init.depth_mode = sl.DEPTH_MODE.NEURAL_PLUS
```

`NEURAL_PLUS` is suitable when measurement quality is more important than raw speed. It can provide stronger depth estimation in difficult scenes, but it requires more compute.

You can change the depth mode depending on your hardware and measurement requirements.

### Depth Mode Comparison

| Depth Mode | Main Advantage | Main Trade-Off |
|---|---|---|
| `PERFORMANCE` | Fastest option | Lower depth quality |
| `ULTRA` | Higher quality classical stereo depth | More compute than performance mode |
| `NEURAL` | Better depth completion and robustness | Requires more GPU resources |
| `NEURAL_PLUS` | Stronger neural depth quality | Highest computational demand |

For measurement tasks, `NEURAL`, `NEURAL_PLUS`, or `ULTRA` are usually better than `PERFORMANCE`, especially when small objects, underwater features, or low-texture surfaces are involved.

## Confidence Thresholding

Depth confidence is critical for reliable measurement.

The script uses ZED runtime parameters to reject uncertain depth samples:

```python
runtime = sl.RuntimeParameters(confidence_threshold=95)
```

A higher confidence threshold forces the system to accept only more reliable depth estimates. This reduces noisy measurements caused by:

- Underwater turbidity.
- Poor lighting.
- Light scattering.
- Specular reflection.
- Low-texture surfaces.
- Invalid stereo matches.
- Unstable depth boundaries.

However, setting the confidence threshold too high can also remove too many points from the depth map, especially in difficult scenes.

### Confidence Threshold Behavior

| Confidence Setting | Effect |
|---|---|
| Lower threshold | More depth points, but more noise |
| Higher threshold | Fewer depth points, but higher reliability |

For precise measurement, it is usually better to start with a higher confidence threshold, then reduce it only if the target disappears from the depth map.

## Texture Confidence

Texture confidence is also important in stereo measurement. Stereo depth estimation depends on matching visual patterns between the left and right camera views. If the object surface has weak texture, repetitive patterns, glare, or poor contrast, the depth estimate may become unstable.

You can tune texture confidence in the ZED runtime parameters when needed.

Example:

```python
runtime = sl.RuntimeParameters()
runtime.confidence_threshold = 95
runtime.texture_confidence_threshold = 100
```

The exact value should be adjusted based on the scene.

### Texture Confidence Behavior

| Texture Confidence Setting | Effect |
|---|---|
| Lower value | Accepts more low-texture regions but may increase noise |
| Higher value | Rejects weak-texture regions but improves reliability |

For accurate measurement, the selected object should be clearly visible in both the RGB image and the depth map.

## Object Visibility in the Depth Map

For accurate measurement, the object must be visible in the depth map.

A point may look clear in the RGB image but still fail in the depth map if the ZED cannot compute reliable disparity at that location. This can happen because of:

- Transparent surfaces.
- Reflective surfaces.
- Low texture.
- Motion blur.
- Turbid water.
- Poor illumination.
- Edge pixels between foreground and background.
- Very small or thin objects.
- Objects outside the reliable depth range.

If the object is not visible or stable in the depth panel, the measurement should not be trusted.

A valid measurement requires both selected points to have reliable 3D coordinates in the point cloud.

## Local Median Sampling Around the Pixel

Measuring distance from a single depth pixel can be unstable. A single pixel may contain noise, invalid depth, or an edge artifact. To reduce this problem, the tool samples a small window around the clicked pixel instead of using one raw point.

The intended robust approach is to use a local median estimate around the selected pixel:

```text
selected_point = median(valid_3D_points_inside_local_window)
```

This suppresses outliers while preserving the local position of the measured feature.

The uploaded script uses a configurable local sampling window:

```python
AVG_WIN = 5
MIN_SAMPLES = 5
```

This means the system samples a `5 × 5` area around the clicked pixel and requires at least `5` valid 3D points before accepting the measurement.

In the current implementation, valid 3D samples are averaged:

```python
return np.mean(np.array(pts, dtype=np.float32), axis=0)
```

For stronger outlier rejection, this can be changed to median filtering:

```python
return np.median(np.array(pts, dtype=np.float32), axis=0)
```

Median filtering is recommended when the scene contains noisy depth, edge artifacts, underwater distortion, or unstable point-cloud values.

## Why Window-Based Sampling Improves Measurement

Window-based sampling improves measurement because it avoids depending on one potentially unstable pixel.

It helps reduce errors from:

- Random depth noise.
- Missing depth pixels.
- Depth discontinuities.
- Small hand-clicking errors.
- Stereo mismatch artifacts.
- Underwater scattering.
- Texture-related instability.

Instead of asking whether one pixel is correct, the tool checks whether enough neighboring pixels provide valid 3D data. This makes the measured point more stable.

## Euclidean 3D Distance Calculation

After two valid 3D points are selected, the program calculates the real-world distance using the Euclidean norm:

```python
dist_cm = float(np.linalg.norm(point_2 - point_1) * 100.0)
```

Because the ZED point cloud is configured in meters:

```python
init.coordinate_units = sl.UNIT.METER
```

The result is multiplied by `100` to convert meters to centimeters.

This gives a direct 3D measurement, not a 2D pixel-based estimate.

## Key Features

### Dual RGB and Depth Interface

The program displays the RGB image and depth map side by side. This allows the operator to confirm both the visual target and the depth availability before measuring.

### Click on RGB or Depth Panel

The user can click on either panel:

- RGB panel for easier visual target selection.
- Depth panel for checking whether the object has valid depth.

Both panels map back to the same ZED point cloud coordinates.

### ZED Point-Cloud Measurement

The system retrieves XYZ coordinates from:

```python
sl.MEASURE.XYZRGBA
```

Each valid selected point is represented as a real 3D coordinate:

```text
X, Y, Z
```

This allows true spatial distance measurement between two points.

### Confidence-Based Filtering

The runtime confidence threshold rejects unreliable depth estimates before measurement, improving robustness in difficult environments.

### Local Window Sampling

A small window around each clicked pixel is sampled to avoid unstable single-pixel measurements.

### Median or Average Spatial Filtering

The local region can be processed using average filtering or median filtering. Median filtering is better for rejecting outliers, while average filtering is simple and smooth.

### Minimum Valid Sample Requirement

The program requires a minimum number of valid point-cloud samples before accepting a selected point.

```python
MIN_SAMPLES = 5
```

If not enough valid samples exist, the point is rejected and the user is asked to select another area.

### Freeze Mode

The user can freeze the display to measure a static frame more accurately.

```text
f = freeze
r = resume
```

Freeze mode is useful when the camera is moving or the scene is changing.

### SVO Recording

The program supports ZED SVO recording:

```text
p = start / stop recording
```

Recorded files are saved in:

```text
svo_recording/
```

This allows measurements to be reviewed later or processed offline.

### SVO Playback

The program supports reading from an existing SVO file:

```bash
python zed_distance_tool.py --input_svo_file path/to/file.svo
```

It also supports starting from a specific frame:

```bash
python zed_distance_tool.py --input_svo_file path/to/file.svo --start_frame 500
```

This is useful when analyzing a specific moment in a recorded experiment.

### ZED Streaming Support

The script can receive a ZED stream using:

```bash
python zed_distance_tool.py --stream 192.168.1.50:30000
```

This is useful when the ZED camera is connected to another machine, such as a robot, Jetson, or remote processing unit.

### Snapshot Saving

The user can save the current RGB frame:

```text
s = save snapshot
```

Snapshots are saved in:

```text
screenshots/
```

### Live Measurement Overlay

The program overlays:

- Selected point labels.
- Connecting measurement line.
- Distance in centimeters.
- Live or frozen status.
- Recording indicator.
- User control hints.

## Controls

| Key / Action | Function |
|---|---|
| Left mouse click | Select a point on RGB or depth panel |
| `f` | Freeze the current display |
| `r` | Resume live display after freezing |
| `c` | Clear selected points and distance |
| `p` | Start or stop SVO recording |
| `s` | Save RGB snapshot |
| `q` | Quit |

## Installation

Install the ZED SDK from Stereolabs before running this project.

Then install the required Python dependencies:

```bash
pip install opencv-python numpy
```

You also need the ZED Python API installed and correctly linked to your ZED SDK installation.

The script imports:

```python
import pyzed.sl as sl
```

If this import fails, the ZED Python API is not installed correctly.

## Suggested Requirements File

Create a `requirements.txt` file:

```text
opencv-python
numpy
```

The ZED Python API is usually installed through the ZED SDK tools rather than pip, depending on your SDK version and operating system.

## Usage

### Run With Local ZED Camera
Run the sender script first either on laptop on jetson 

```bash
python zed_distance_tool.py
```

### Run With ZED Stream

```bash
python zed_distance_tool.py --stream 192.168.1.50:30000
```

### Run With SVO File

```bash
python zed_distance_tool.py --input_svo_file recording.svo
```

### Start SVO Playback From a Specific Frame

```bash
python zed_distance_tool.py --input_svo_file recording.svo --start_frame 500
```

## Recommended Measurement Workflow

1. Open the ZED camera, stream, or SVO file.
2. Confirm that the target is visible in the RGB panel.
3. Confirm that the target is also visible and stable in the depth panel.
4. Adjust confidence threshold if the depth map is too noisy or too sparse.
5. Adjust texture confidence if the object has weak texture or unstable depth.
6. Select the first point on either the RGB or depth panel.
7. Select the second point on either panel.
8. Read the measured distance in centimeters.
9. Use freeze mode when measuring moving scenes or unstable camera footage.
10. Save screenshots or SVO recordings for documentation.

## Calibration Notes

For best measurement results, the ZED camera should be calibrated correctly.

In underwater environments, calibration can become more complex because the camera housing, refraction, and water medium can affect the optical path.

The script includes optional support for custom OpenCV calibration:

```python
init.optional_opencv_calibration_file = "calibration_underwater.yaml"
```

For workflows where you want to rely on a custom underwater calibration, you may disable self-calibration:

```python
init.camera_disable_self_calib = True
```

This should only be done when the custom calibration file is reliable.

## Measurement Accuracy Considerations

Measurement accuracy depends on several factors:

- ZED calibration quality.
- Depth mode.
- Confidence threshold.
- Texture confidence threshold.
- Object visibility in the depth map.
- Distance between camera and target.
- Lighting conditions.
- Surface texture.
- Reflections.
- Water clarity.
- Camera stability.
- Correct point selection.
- Local window size.
- Whether median or average filtering is used.

The measured value should be considered reliable only when both selected points have stable depth values.

## Underwater Measurement Considerations

Underwater measurement is more difficult than measurement in air because the scene may contain:

- Turbidity.
- Suspended particles.
- Light scattering.
- Reduced contrast.
- Color attenuation.
- Refraction through the camera housing.
- Specular reflection from wet or smooth surfaces.
- Moving water.
- Reduced texture visibility.

For underwater measurements, it is recommended to:

1. Use strong and even lighting.
2. Avoid reflective surfaces where possible.
3. Keep the camera stable.
4. Use `NEURAL`, `NEURAL_PLUS`, or `ULTRA` depth mode.
5. Use higher confidence thresholds.
6. Use local median filtering.
7. Verify that the object is visible in the depth map before measuring.
8. Capture SVO recordings for offline review.

## Suggested Repository Structure

```text
project-folder/
│
├── zed_distance_tool.py
├── README.md
├── requirements.txt
│
├── videos/
│   ├── small-pipes-measurement.mp4
│   └── target-10cm-measurement.mp4
│
├── screenshots/
│   └── saved snapshots
│
└── svo_recording/
    └── recorded SVO files
```


## Limitations

This tool depends on valid stereo depth. It cannot measure accurately if the ZED camera cannot reconstruct the selected points in 3D.

The tool may fail or produce unstable measurements when:

- The object is not visible in the depth map.
- The target surface has weak texture.
- The object is reflective or transparent.
- The selected point lies on a depth boundary.
- The camera is too close or too far from the target.
- The scene contains motion blur.
- The lighting is poor.
- The water is highly turbid.
- The ZED calibration is inaccurate.

The system is designed to improve practical measurement stability, but it does not remove the need for correct camera setup, calibration, and scene validation.

## Notes

The key idea behind this project is that reliable depth measurement should not depend on a single clicked pixel. By combining ZED SDK depth tuning, confidence filtering, texture validation, local point-cloud sampling, and Euclidean 3D distance calculation, the system provides a more stable and practical approach for centimeter-level measurement tasks.

The object must be visible in the depth map for the measurement to be trusted. If the depth panel does not clearly represent the target, the RGB image alone is not enough for accurate 3D measurement.
