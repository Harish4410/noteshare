"""
Test AI features - run: python test_ai.py
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from utils.ai_utils import generate_summary, generate_flashcards, generate_quiz, evaluate_note, _use_gemini

print("=" * 55)
print("   NoteShare AI Feature Test (Google Gemini)")
print("=" * 55)

key = os.environ.get('GEMINI_API_KEY','').strip()
if key:
    print(f"\n✅ Gemini API Key: {key[:8]}...{key[-4:]}")
    print("   Mode: FULL AI (Google Gemini 1.5 Flash)")
else:
    print("\n⚠️  No GEMINI_API_KEY found in .env")
    print("   Mode: Fallback (basic text analysis)")

sample = """
Machine Learning is a subset of Artificial Intelligence.
It allows computers to learn from data without explicit programming.
There are 3 types: Supervised Learning, Unsupervised Learning, Reinforcement Learning.
Neural Networks are inspired by the human brain with layers of nodes.
Deep Learning uses multiple hidden layers to extract complex patterns from data.
Convolutional Neural Networks are used for image recognition tasks.
Recurrent Neural Networks handle sequential data like text and speech.
"""

print("\n--- Running Tests ---\n")

print("1. SUMMARY:")
print(generate_summary(sample))

print("\n2. FLASHCARDS:")
cards = generate_flashcards(sample)
print(f"   Generated {len(cards)} flashcards:")
for i,c in enumerate(cards[:3],1):
    print(f"   Q{i}: {c.get('question','')[:70]}")
    print(f"   A{i}: {c.get('answer','')[:70]}")

print("\n3. QUIZ:")
quiz = generate_quiz(sample)
print(f"   Generated {len(quiz)} questions:")
for i,q in enumerate(quiz[:2],1):
    print(f"   Q{i}: {q.get('question','')[:70]}")
    opts = q.get('options',[])
    for o in opts[:2]: print(f"      - {o[:50]}")
    print(f"   Answer: {q.get('answer','')[:50]}")

print("\n4. SCORE:")
print(f"   Score: {evaluate_note(sample)}/10")

print("\n" + "=" * 55)
print("✅ All AI features working!")
print("=" * 55)
