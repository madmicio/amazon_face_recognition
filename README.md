# Amazon Face Recognition for Home Assistant

Amazon Face Recognition is a Home Assistant custom integration that adds **face recognition** and **object detection** capabilities using **AWS Rekognition**.

This project is inspired by the work of **robmarkcole** and his original integration:
- https://github.com/robmarkcole
- https://github.com/robmarkcole/HASS-amazon-rekognition

The original project focused primarily on **object detection** using Amazon Rekognition.

---

## Project origin and evolution

While this integration takes inspiration from the original work, the **codebase has been completely rewritten** and significantly expanded.

Starting from the original concept of object detection, this project introduces a full **face recognition system**, transforming the integration into a comprehensive solution for people recognition and automation in Home Assistant.

### Major differences from the original project

Compared to the original integration, this project adds:

- 👤 **Face recognition using AWS Rekognition Face Collections**
- 🗂 **Face collection management**
- 🔧 **Home Assistant services** to:
  - index new faces
  - delete faces by name
  - delete all faces from a collection
- 📊 **Dedicated entities and sensors** that:
  - expose recognized users stored in AWS
  - provide real-time information about detected and recognized persons
- ⚡ **Entities specifically designed for automations**
  - making it easy to trigger actions based on who is recognized
- 🖼 **Annotated snapshots** with face and person bounding boxes
- 🧾 **Recognition history index** stored as JSON

The result is an integration that goes beyond simple detection and enables **identity-based automations** inside Home Assistant.

---

## Companion Custom Card

To complete the experience, a dedicated **custom Lovelace card** has been developed specifically for this integration:

👉 https://github.com/madmicio/aws-face-recognition-card

The custom card allows you to:
- visually display recognition results
- browse saved snapshots
- see recognized and unrecognized people
- manage recognition data directly from the Home Assistant UI

Together, the integration and the custom card provide a **complete face recognition ecosystem** for Home Assistant.

![Amazon Face Recognition Dashboard](images/es.1.png)

---

It allows Home Assistant to:
- Detect people in camera images
- Recognize known faces
- Save annotated snapshots
- Expose events and sensors for automations

This integration is designed to be powerful but **easy to use**, even if you are not familiar with AWS.

---

## Features

- ✅ Face recognition using AWS Rekognition
- ✅ Person and object detection
- ✅ Annotated image snapshots with bounding boxes
- ✅ JSON index with recognition history
- ✅ Home Assistant services to manage faces
- ✅ Sensors for recognized persons
- ✅ Fully compatible with HACS

---

## Requirements

- Home Assistant
- An AWS account (Free Tier supported)
- AWS Rekognition enabled
- Internet access

---

## Installation (HACS)

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Add this repository as a **custom repository**
4. Search for **Amazon Face Recognition**
5. Install and restart Home Assistant

---

## Getting started with AWS

Before using this integration, you need to configure AWS.

### 1. Sign up for an AWS account

To use Amazon Face Recognition, you first need an AWS account.  
AWS provides **12 months of Free Tier access**, which is enough for testing and light usage.

1. Open:  
   https://portal.aws.amazon.com

2. Fill in:
   - Email address
   - Password
   - AWS account name

3. Enter your address and phone number.

4. Add a **credit or debit card**  
   - A temporary charge of **1 USD / EUR** may be applied for verification.
   - The amount is refunded after a few days.
   - No extra charges apply if you stay within the Free Tier limits.

5. Verify your phone number with the code sent by AWS.

6. Select the **Basic Free Plan**.

> ⚠️ A paid plan is **not required** for this integration.

---

## Create an Amazon Face Recognition IAM User

For security reasons, Home Assistant should **not** use the root AWS account.

We will create a dedicated user using **AWS Identity and Access Management (IAM)**.

### Step 1 – Open IAM

1. Log in to the AWS Console.
2. Search for **IAM (Identity and Access Management)** and open it.

> 🔐 Strongly recommended: enable **MFA (Multi-Factor Authentication)** on your AWS account.

---

### Step 2 – Create a new user

1. Go to **Users** → **Add users**
2. Choose a username (example: `homeassistant-face-recognition`)
3. Select:
   - ✅ **Programmatic access**
4. Click **Next**

---

### Step 3 – Assign permissions

1. Select **Attach existing policies directly**
2. Search for **Rekognition**
3. Select:
   - ✅ `AmazonRekognitionFullAccess`
4. Click **Next**

---

### Step 4 – Save credentials (IMPORTANT)

After creating the user, AWS will show:

- **Access Key ID**
- **Secret Access Key**

⚠️ Save them now.  
You will need them in Home Assistant and **AWS will not show the secret key again**.

---

## Create a Face Collection and get the Collection ID

A **face collection** is where Amazon Face Recognition stores the faces you want to recognize.

You only need **one collection**.

### Step 1 – Open Amazon Rekognition

1. In the AWS Console, search for **Rekognition**
2. Make sure the selected **region** matches the one you will use in Home Assistant

> ⚠️ In AWS, the service is still called **Amazon Rekognition**.

---

### Step 2 – Create the collection

1. Open **Face collections**
2. Click **Create collection**
3. Enter a Collection ID  
   Example:
4. Click **Create**

---

### Step 3 – Copy the Collection ID

📌 The **Collection ID** is the name you chose (e.g. `homeassistant_faces`).

⚠️ Do **not** use the Collection ARN.  
Home Assistant only needs the **Collection ID**.

---

## Home Assistant configuration

Below is a complete configuration example with **all supported options**:

```yaml
image_processing:
  - platform: amazon_face_recognition
    aws_access_key_id: XXXXXXXXXXXXXXXXXXXXXXXXXXX
    aws_secret_access_key: XXXXXXXXXXXXXXXXXXXXXXX
    region_name: eu-west-1
    collection_id: homeassistant_faces

    targets:
      - target: person
      - target: car
        confidence: 50

    source:
      - entity_id: camera.camera_test_rekognition

    save_file_format: jpg   # jpg or png
    save_file_folder: /config/www/snapshots/
    save_timestamped_file: true

    s3_bucket: homeassistant-bucket-253490766504

    always_save_latest_file: true
    max_saved_files: 10

    label_font_scale: 0.026
    max_red_boxes: 10
    min_red_box_area: 0.02
```
### Restart Home Assistant after saving.



## Configuration options explained
- ### platform (required)

    amazon_face_recognition
    The name of this integration platform.
    Make sure it matches the integration domain.

- ### aws_access_key_id (required)

    Your AWS Access Key ID created in IAM.

- ### aws_secret_access_key (required)

    Your AWS Secret Access Key created in IAM.

        ⚠️ Keep this secret. Do not share it and do not publish it on GitHub.

- ## region_name (required)

    The AWS region used by Rekognition, for example:

        eu-west-1

        eu-central-1

        us-east-1

    The region must match the region where your face collection exists.

- ## collection_id (optional, but required for face recognition)

    The Face Collection ID used for face recognition.

    Example: homeassistant_faces

    - If you set collection_id, the integration will try to recognize faces using that collection.

    - If you leave it empty, the integration will still detect objects/people but faces will not be recognized.

- ## targets (optional)

    List of objects you want AWS Rekognition to detect.

    Example:
    ```yaml
    targets:
      - target: person
      - target: car
          confidence: 50
    ```


        - target: object name (example: person, car, dog, etc.)

        - onfidence: optional per-target confidence threshold (10–100)

    If confidence is not set for a target, the integration will use the global confidence value (if configured) or AWS defaults.


- ## source (required)

    The camera entities to process.

    Example:
    ```yaml
    source:
      - entity_id: camera.front_door
    ```

- ## Snapshot saving options
    save_file_format (optional)

    Image format for saved snapshots:

    - jpg (default)

    - png

- ## save_file_folder

    Folder where annotated snapshots are stored.

    Example:   
    ```yaml  
    save_file_folder: /config/www/snapshots/
    ```

- ##  save_timestamped_file (optional)

    If true, the integration saves a timestamped file name:

    recognition_YYYYMMDD_HHMMSS.jpg

- ## always_save_latest_file (optional)

    If true, the integration saves an image even when no targets are detected (useful for debugging or for a “latest snapshot” view).

    If false, snapshots are saved only when something is detected.

- ## max_saved_files (optional)

    Maximum number of saved snapshot files to keep in save_file_folder.

    Old files will be automatically deleted.
    Default: 10

- ## S3 options (optional)
    s3_bucket (optional)

    If set, snapshots can be uploaded to an S3 bucket.

    Example:
    ```yaml
    s3_bucket: my-homeassistant-bucket
    ```

The IAM user must have S3 permissions for that bucket.

- ## Drawing and label tuning

    These options control how bounding boxes and labels are rendered in snapshots.

    label_font_scale (optional)

    Controls the label text size (relative to image size).

    Lower value = smaller text

    Higher value = larger text

    Default: 0.020

    Example:
    ```yaml
    label_font_scale: 0.026
    ```

- ## max_red_boxes (optional)

    Maximum number of red boxes drawn for “person” detections that are not recognized.

    Default: 6

    Example:
    ```yaml
    max_red_boxes: 10
    ```
    Set to 0 to disable red boxes.

- ## min_red_box_area (optional)

    Filters out very small person boxes (to reduce false positives).
    Value is normalized (0.0–1.0) relative to the image area.

    Default: 0.03

    Example:
```yaml
    min_red_box_area: 0.02
```



## After configuration

    - Restart Home Assistant

    - Check the created entities under Developer Tools → States

    - Use the services to add faces to your collection:

        - amazon_face_recognition.index_face

        - amazon_face_recognition.delete_faces_by_name

        - amazon_face_recognition.delete_all_faces

# Add faces to the collection (recommended)

This integration provides Home Assistant services to manage faces.

Index a new face
```yaml
service: amazon_face_recognition.index_face
data:
  file_path: /config/www/faces/mario.jpg
  name: Mario
```
### Tips for best results

- at least one face per image
- at least one Frontal face
- Good lighting
- JPG or PNG format
- Multiple images and different angles per person improve accuracy

# Face management services
## Delete all faces for a person
```yaml
service: amazon_face_recognition.delete_faces_by_name
data:
  name: Mario
```
## Delete all faces in the collection

```yaml
service: amazon_face_recognition.delete_all_faces
```

# Sensors and Events

This integration provides:

A sensor with the last recognized person

Events for detected objects and faces

Optional annotated snapshots with bounding boxes

These can be used in automations and dashboards.

![Amazon Face Recognition entity](images/sensor.png)
etc.etc

# Notes about costs

Amazon Rekognition is a paid AWS service, but:

The Free Tier is usually enough for testing

Costs depend on the number of images processed

Always monitor usage in the AWS Console

Pricing details:
https://aws.amazon.com/rekognition/pricing/

USD 0.001 per scan (1,000 scans = USD 1)

12 months free (AWS Free Tier)



# Troubleshooting

Make sure the AWS region matches everywhere

Use clear images with a single face

Check that the Collection ID is correct

Verify IAM permissions

# Disclaimer

This project is not affiliated with Amazon or AWS.
Amazon Rekognition is a trademark of Amazon Web Services.