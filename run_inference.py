import json
import sys
import os
from datetime import datetime

# Ensure src is in the system path for relative imports if run as a script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from scraper.inference.engine import infer_tasks_from_chat

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_inference.py <scraped_messages_json_path>")
        return

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        # Try local path if relative fails
        alternate_path = os.path.join(os.getcwd(), input_path)
        if not os.path.exists(alternate_path):
            print(f"Error: File {input_path} not found.")
            return
        input_path = alternate_path

    print(f"Loading data from {input_path}...")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # The scraping output format from our current project
    if isinstance(data, dict) and "chats" in data:
        chats = data["chats"]
    elif isinstance(data, list):
        chats = data
    else:
        print("Error: Unknown scraping output format.")
        return

    all_inferred_tasks = []
    print(f"Found {len(chats)} chats in the input file.")

    for chat in chats:
        chat_name = chat.get("name", chat.get("chat_name", "Unknown Chat"))
        messages = chat.get("messages", [])
        
        if not messages:
            print(f"Skipping '{chat_name}': No messages found.")
            continue
            
        print(f"Processing chat '{chat_name}' with {len(messages)} messages...")
        try:
            tasks = infer_tasks_from_chat(chat_name, messages)
            print(f" - Inferred {len(tasks)} tasks.")
            all_inferred_tasks.extend(tasks)
        except Exception as e:
            print(f" - Error processing chat '{chat_name}': {e}")

    # Create output directory if it doesn't exist
    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    # Save output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"tasks_inferred_{timestamp}.json"
    output_path = os.path.join("outputs", output_filename)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_inferred_tasks, f, indent=2, ensure_ascii=False)
        
    print(f"\n" + "="*50)
    print(f"Final Count: {len(all_inferred_tasks)} tasks.")
    print(f"Output saved to: {output_path}")
    print("="*50)

if __name__ == "__main__":
    main()
