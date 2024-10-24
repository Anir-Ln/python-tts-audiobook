
from unittest.mock import Mock
from main import TTS, AudioBookGenerator, AudioHelper, Book, Chapter
import asyncio

chapter_1 = Chapter(
    0, 
    "The Dawn of Exploration - Part 1", 
    [
        "In the early days of human civilization, exploration was driven by the curiosity of the unknown. People set sail on uncharted waters, climbed towering mountains, and crossed vast deserts without knowing what awaited them. Each discovery opened new horizons and new opportunities for knowledge and growth. It was not just about survival; it was about expanding the boundaries of human experience.",
        
        "Fast forward to today, and the spirit of exploration still burns brightly, but the frontiers have shifted. Instead of navigating the physical world, we now explore the digital, the virtual, and even the microscopic. Scientists peer into the depths of space with telescopes that can see billions of light-years away. Engineers build machines that can think and learn, pushing the limits of what technology can achieve. The possibilities are as endless as they once were for the early explorers."
    ]
)
chapter_2 = Chapter(
    1, 
    "The Dawn of Exploration - Part 2", 
    [
        "However, exploration comes with its own challenges, both physical and moral. What responsibilities do we hold as we push the boundaries of knowledge? How do we balance the drive to discover with the need to protect the world and the creatures we share it with? These questions have become more pressing as technology continues to evolve at an ever-accelerating pace. Every step forward requires careful consideration of the impact we have on the world and its future.",
        
        "In the end, the true essence of exploration lies not in the discovery itself but in the journey. Each new challenge we face teaches us something about ourselves, about our limitations, and about the power of persistence and creativity. Whether it is in the realms of science, technology, or personal growth, exploration remains a fundamental part of what makes us human. It is the drive to learn, to grow, and to understand the universe and our place within it."
    ]
)


def test():
  tts = TTS()
  book = Mock()
  metadata = {"title": "The best book", "creator": "anir", "date": "25-10-2024"}
  book.title = metadata["title"]
  book.chapters = [chapter_1, chapter_2]
  book.get_metadata_text.return_value = (";FFMETADATA1\n"
                                        "major_brand=M4A\n"
                                        "minor_version=512\n"
                                        "compatible_brands=M4A isomiso2\n"
                                        f"title={metadata['title']}\n"
                                        f"artist={metadata['creator']}\n"
                                        f"album={metadata['title']}\n"
                                        f"date={metadata['date']}\n"
                                        "genre=Audiobook\n"
                                        )

  b2audio = AudioBookGenerator(book, tts)
  asyncio.run(b2audio.generate())