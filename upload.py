import json
import os
import subprocess
from datetime import date
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# Files with overlays already burned in — skip hook addition
SKIP_HOOK = {
    "Amazon Seller Success_ 87 Cases Won!.mp4",
    "Son of Janitor to Bodybuilding Pro_ My Dream Story.mp4",
    "Cancer Diagnosis Sparks Purpose_ Building a Brand for Legacy.mp4",
    "FIND YOUR COACH_ Unlock Your Athlete Career Potential NOW!.mp4",
    "Never Eat Alone! Your Next Big Break Could Be There.mp4",
    "Future Proof Your Career_ The 10-Year Plan Secret.mp4",
}

creds = Credentials.from_authorized_user_file("token.json", [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/drive.readonly"
])

with open("YOUTUBE_SCHEDULE.json") as f:
    schedule = json.load(f)

today = str(date.today())
todays_posts = [s for s in schedule if s["post_date"] == today]

if not todays_posts:
    print(f"No posts scheduled for {today}. Done.")
    exit()

drive = build("drive", "v3", credentials=creds)
youtube = build("youtube", "v3", credentials=creds)

for post in todays_posts:
    title = post["copy"]["youtube_title"]
    hook = post["copy"]["hook"]
    print(f"Processing: {title}")

    filename = os.path.basename(post["path"])
    
    # Force 9:16 path to ensure correct format
    correct_path = post["path"].replace("16:9 (YouTube)", "9:16 (Instagram, LinkedIn)")
    correct_filename = os.path.basename(correct_path)
    
    # Search for file in the correct 9:16 folder path
    folder_path = os.path.dirname(correct_path)
    results = drive.files().list(
        q=f"name='{correct_filename}' and '{folder_path}' in parents",
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])

    # Fallback: search by filename only
    if not files:
        results = drive.files().list(
            q=f"name='{correct_filename}'",
            fields="files(id, name)"
        ).execute()
        files = results.get("files", [])

    if not files:
        print(f"  File not found in Drive: {correct_filename}")
        continue

    file_id = files[0]["id"]
    request = drive.files().get_media(fileId=file_id)
    with open(correct_filename, "wb") as f:
        f.write(request.execute())
    print(f"  Downloaded: {correct_filename}")

    if correct_filename in SKIP_HOOK:
        print(f"  Skipping hook overlay (pre-rendered overlay exists)")
        upload_filename = correct_filename
    else:
        hook_clean = hook.replace("'", "\\'")
        if '.' in hook_clean[:-1]:
            split = hook_clean.index('.') + 1
            line1 = hook_clean[:split].strip()
            line2 = hook_clean[split:].strip()
        else:
            words = hook_clean.split()
            mid = len(words) // 2
            line1 = ' '.join(words[:mid])
            line2 = ' '.join(words[mid:])

        hooked_filename = f"hooked_{correct_filename}"
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', correct_filename,
            '-vf',
            f"drawbox=x=20:y=20:w=680:h=160:color=white@0.95:t=fill,"
            f"drawtext=text='{line1}':fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf:fontsize=44:fontcolor=black:x=40:y=38,"
            f"drawtext=text='{line2}':fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf:fontsize=44:fontcolor=black:x=40:y=98",
            '-c:a', 'copy',
            hooked_filename
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ffmpeg error: {result.stderr[-500:]}")
            continue
        print(f"  Hook overlay added")
        upload_filename = hooked_filename

    body = {
        "snippet": {
            "title": title,
            "description": post["copy"]["youtube_description"],
            "tags": post["copy"]["hashtags"].replace("#", "").split(),
            "categoryId": "17"
        },
        "status": {"privacyStatus": "public"}
    }

    media = MediaFileUpload(upload_filename, mimetype="video/mp4", resumable=True)
    response = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    ).execute()

    print(f"  Uploaded: https://youtube.com/watch?v={response['id']}")
    os.remove(correct_filename)
    if upload_filename != correct_filename and os.path.exists(upload_filename):
        os.remove(upload_filename)

print("Done.")
