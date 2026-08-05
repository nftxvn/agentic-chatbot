import os
import sys

# Add the current directory to sys.path so we can import 'app'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.embedding_service import get_chroma_collection

def main():
    try:
        collection = get_chroma_collection()
        
        # Get all documents
        results = collection.get()
        
        ids = results.get('ids', [])
        metadatas = results.get('metadatas', [])
        documents = results.get('documents', [])
        
        output_file = "chroma_db_contents.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# ChromaDB Contents Dump\n\n")
            f.write(f"**Collection Name:** {collection.name}  \n")
            f.write(f"**Total Documents:** {collection.count()}  \n\n")
            
            if not ids:
                f.write("ChromaDB is empty.\n")
                return

            f.write("## Vectors\n\n")
            
            for i in range(len(ids)):
                f.write(f"### [{i+1}] ID: `{ids[i]}`\n\n")
                
                f.write("**Metadata:**\n")
                f.write("```json\n")
                # format metadata as pretty json
                import json
                f.write(json.dumps(metadatas[i], indent=2))
                f.write("\n```\n\n")
                
                f.write("**Document Content:**\n")
                f.write("```text\n")
                f.write(documents[i] if documents[i] else "None")
                f.write("\n```\n\n")
                f.write("---\n\n")
                
        print(f"Successfully dumped ChromaDB contents to {output_file}")
            
    except Exception as e:
        print(f"Error viewing ChromaDB: {e}")

if __name__ == "__main__":
    main()
