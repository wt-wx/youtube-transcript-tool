import json
import argparse
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

def get_transcript(video_id, languages=['zh-Hans', 'zh-CN', 'en']):
    """
    Fetch the transcript for a given YouTube video ID.
    """
    try:
        # Create an instance of the API
        api = YouTubeTranscriptApi()
        
        # Fetch the transcript list
        transcript_list = api.list(video_id)
        
        # Try to find the transcript in the requested languages
        try:
            transcript = transcript_list.find_transcript(languages)
            return transcript.fetch().to_raw_data()
        except Exception:
            # If no manual transcript, try finding a generated one
            print(f"No manual transcript found for {video_id} in {languages}. Searching for auto-generated...")
            transcript = transcript_list.find_generated_transcript(languages)
            return transcript.fetch().to_raw_data()
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

def save_transcript(transcript, filename):
    """Save transcript to a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)
    print(f"Transcript saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube transcripts easily.")
    parser.add_argument("video_url", help="YouTube video URL or ID")
    parser.add_argument("--lang", nargs='+', default=['zh-Hans', 'zh-CN', 'en'], help="Language codes")
    parser.add_argument("--out", help="Output filename (default: <video_id>.json)")
    
    args = parser.parse_args()
    
    # Extract video ID from URL if necessary
    video_id = args.video_url
    if "youtube.com/watch?v=" in video_id:
        video_id = video_id.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_id:
        video_id = video_id.split("/")[-1].split("?")[0]
        
    print(f"Fetching transcript for video ID: {video_id}...")
    transcript = get_transcript(video_id, args.lang)
    
    if transcript:
        output_file = args.out if args.out else f"{video_id}.json"
        save_transcript(transcript, output_file)
    else:
        print("Failed to retrieve transcript.")

if __name__ == "__main__":
    main()
