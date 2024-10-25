import io
from ebooklib import epub
import epub_metadata
from bs4 import BeautifulSoup
import asyncio
import edge_tts
import sys
import os
from pydub import AudioSegment
from typing import List
import subprocess

### CONSTANTS ###
PARAGRAPH_PAUSE_DURATION = 500
CHAPTER_TITLE_PAUSE_DURATION = 900
CHAPTER_PAUSE_DURATION = 2000
#################


class AudioHelper:
  @staticmethod
  def generate_pause(time: int) -> bytes:
    return AudioSegment.silent(time).raw_data

  @staticmethod
  def insert_pauses(items: List[bytes], time) -> List[bytes]:
    if not items:
      return []
    ret = []
    for item in items[:-1]:
      ret.append(item)
      ret.append(AudioHelper.generate_pause(time))
    ret.append(items[-1])
    return ret

  @staticmethod
  def bytes2audio(audio_bytes: io.BytesIO):
    audio_bytes.seek(0)
    return AudioSegment.from_raw(
        audio_bytes, sample_width=2, frame_rate=24000, channels=1
    )


class Chapter:
  def __init__(self, id: int, title: str, paragraphs: List[str]):
    self.id = id
    self.title = title if title else f"chapter-{self.id}.mp3"
    self.paragraphs = paragraphs
    self.start_time = None
    self.end_time = None

  def get_metadata_text(self):
    if self.start_time == None or self.end_time == None:
      print("ERROR, chapter time is NONE",
            self.start_time, self.end_time)
    return (
        "\n[CHAPTER]\n"
        "TIMEBASE=1/1000\n"
        f"START={self.start_time}\n"
        f"END={self.end_time}\n"
        f"title={self.title}\n"
    )


class Book:
  def __init__(self, file_path: str):
    self.file_path = file_path
    self.metadata = epub_metadata.epub(file_path).metadata
    self.title = self.metadata.title
    self.chapters: List[Chapter] = self.extract_chapters()

  def get_metadata_text(self):
    return (
        ";FFMETADATA1\n"
        "major_brand=M4A\n"
        "minor_version=512\n"
        "compatible_brands=M4A isomiso2\n"
        f"title={self.metadata.title}\n"
        f"artist={self.metadata.creator}\n"
        f"album={self.metadata.title}\n"
        f"date={self.metadata.date}\n"
        "genre=Audiobook\n"
    )

  def get_chapters_titles(self):
    return list(map(lambda chapter: chapter.title, self.chapters))

  def extract_chapters(self) -> tuple[List[Chapter], dict]:
    book = epub.read_epub(self.file_path)
    toc = book.toc
    toc_items: List[epub.Link] = []

    # Helper function to extract titles from TOC
    def extract_toc_items(items):
      for item in items:
        if isinstance(item, epub.Link):
          toc_items.append(item)
        elif isinstance(item, tuple):  # Handle nested TOC
          extract_toc_items(item[1])

    extract_toc_items(toc)

    chapters = []

    # Helper function to extract text content from an epub document
    def extract_paragraphs(item):
      soup = BeautifulSoup(item.get_body_content(), "html.parser")
      paragraphs = [p.get_text() for p in soup.find_all("p")]
      return paragraphs

    # Extract chapter content for the selected range
    for idx, toc_item in enumerate(toc_items):
      for doc_item in book.get_items():
        if doc_item.get_name() == toc_item.href:
          paragraphs = extract_paragraphs(doc_item)
          chapters.append(Chapter(idx, toc_item.title, paragraphs))

    # todo: extract metadata
    return chapters


class TTS:
  def __init__(self, voice: str = "en-US-BrianMultilingualNeural"):
    self.voice = voice

  async def chapter_to_audio(self, chapter: Chapter):
    chapter_bytes = io.BytesIO()
    if chapter.title:
      audio_bytes = await self.generate_audio(chapter.title)
      chapter_bytes.write(audio_bytes)
      chapter_bytes.write(
          AudioHelper.generate_pause(CHAPTER_TITLE_PAUSE_DURATION)
      )
    audio_chunks = AudioHelper.insert_pauses(
        [await self.generate_audio(p) for p in chapter.paragraphs],
        PARAGRAPH_PAUSE_DURATION,
    )
    for chunk in audio_chunks:
      chapter_bytes.write(chunk)
    return chapter_bytes

  async def generate_audio(self, text: str) -> bytes:
    communicate = edge_tts.Communicate(text=text, voice=self.voice)
    audio_bytes = io.BytesIO()
    async for chunk in communicate.stream():
      if chunk["type"] == "audio":
        audio_bytes.write(chunk["data"])
      elif chunk["type"] == "WordBoundary":
        print(f"WordBoundary: {chunk}")
    audio_bytes.seek(0)
    # handle the case where the chunk is empty
    try:
      print(f"Decoding the chunk")
      decoded_chunk = AudioSegment.from_mp3(audio_bytes)
    except Exception as e:
      print(f"Failed to decode the chunk, reason: {
          e}, returning a silent chunk.")
      decoded_chunk = AudioSegment.silent(0)
    return decoded_chunk.raw_data


class AudioBookGenerator:
  def __init__(self, book: Book, tts: TTS):
    self.book = book
    self.tts = tts
    self.start_chapter = 0
    self.end_chapter = len(self.book.chapters) - 1
    self.out_folder = f"./{self.book.title}"
    # create out_folder if not exists
    if not os.path.exists(self.out_folder):
      os.makedirs(self.out_folder)
    if not os.path.exists(self.out_folder + "/chapters"):
      os.makedirs(self.out_folder + "/chapters")

  async def generate(self):
    book_audio = AudioSegment.empty()
    book_ffmetadata = self.book.get_metadata_text()
    time = 0.0
    for chapter in self.book.chapters[self.start_chapter: self.end_chapter + 1]:
      chapter_bytes: io.BytesIO = await self.tts.chapter_to_audio(chapter)
      chapter_audio: AudioSegment = AudioHelper.bytes2audio(
          chapter_bytes)
      print(f"saving {chapter_audio.duration_seconds} seconds")
      chapter_audio.export(
          self.out_folder + "/chapters/" + chapter.title + ".mp3"
      )
      book_audio += chapter_audio
      book_audio += AudioSegment.silent(CHAPTER_PAUSE_DURATION)
      chapter.start_time = time
      chapter.end_time = (
          time + chapter_audio.duration_seconds * 1000 + CHAPTER_PAUSE_DURATION
      )
      time = chapter.end_time
      book_ffmetadata += (
          chapter.get_metadata_text()
      )  # start_time and end_time should be set

    audiobook_path = self.out_folder + "/" + self.book.title + ".m4a"
    book_audio.export(audiobook_path, format="mp4")
    self._bind_metadata(book_ffmetadata, audiobook_path)

  def _bind_metadata(self, metadata, audiobook_path):
    ffmetadata_path = self.out_folder + "/ffmetadata.txt"
    with open(ffmetadata_path, "w") as f:
      print(metadata, file=f)

    cmd = ["ffmpeg", "-y", "-i", audiobook_path, "-i", ffmetadata_path, "-map_metadata", "1", "-map_chapters", "1",
           "-c", "copy", audiobook_path[:-4] + ".m4b"]
    subprocess.run(cmd)


def main():
  # Get the file path from the user
  file_path = input("Please provide the path to the ePub file: ")
  assert file_path.endswith(".epub"), "epub file should have .epub extension"
  tts = TTS("en-US-BrianMultilingualNeural")
  book = Book(file_path)
  book2audio = AudioBookGenerator(book, tts)
  print(book.metadata)
  try:
    # Extract TOC
    toc_titles = book.get_chapters_titles()
    # List available chapters
    print("\nChapters:")
    for i, title in enumerate(toc_titles):
      print(f"{i}: {title}")
    # User chooses start and end chapters
    start_chapter = int(input("\nEnter the start chapter number: "))
    end_chapter = int(input("Enter the end chapter number: "))
    if (
        start_chapter < 0
        or end_chapter > len(toc_titles) - 1
        or start_chapter > end_chapter
    ):
      print("Invalid chapter range. Exiting.")
      sys.exit(1)
    book2audio.start_chapter = start_chapter
    book2audio.end_chapter = end_chapter
    asyncio.run(book2audio.generate())
  except Exception as e:
    print(f"An error occurred: {e}")


if __name__ == "__main__":
  main()
