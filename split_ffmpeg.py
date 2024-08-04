#!/usr/bin/env python3

import os
import re
import string
import sys
import tempfile
from json import JSONDecodeError
import subprocess
from optparse import OptionParser
import json
import shlex


def parse_chapters(filename):
    chapters = []
    command = ["ffprobe", '-i', filename, '-print_format', 'json', '-show_chapters', '-loglevel', 'error']
    output = ""
    try:
        # ffmpeg requires an output file and so it errors
        # when it does not get one so we need to capture stderr,
        # not stdout.
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        output = e.output

    try:
        json_data = json.loads(output)
    except JSONDecodeError:
        raise RuntimeError("Unable to parse JSON '{}'".format(output))

    num = 0
    for chapter in json_data['chapters']:
        num += 1
        title = chapter['tags']['title']
        chapters.append({
            "title": str(title).strip(),
            "number": num,
            "start": chapter['start_time'],
            "end": chapter['end_time'],
        })

    return chapters


def convert_file(input_file, output_file, start_time, end_time, metadata, extra_flags):
    # write metadata for ffmpeg to tmp file to avoid issues with special characters in command line input
    metadata_temp_file = tempfile.NamedTemporaryFile(delete_on_close=False, mode="w", suffix='.txt')
    metadata_str = ";FFMETADATA1\n"
    for key, value in metadata.items():
        metadata_str += '{}={}\n'.format(key, value)
    metadata_temp_file.write(metadata_str)
    metadata_temp_file.flush()

    if extra_flags is not None:
        extra_args = shlex.split(extra_flags)
    else:
        extra_args = [
            '-vcodec', 'copy',
            '-acodec', 'copy',
        ]

    command = [
        'ffmpeg',
        '-hwaccel', 'auto',
        '-v', 'quiet',
        '-y',
        '-i', str(input_file),
        '-i', str(metadata_temp_file.name),
        '-map_chapters', '-1',
        '-map_metadata', '-1',
        '-map_metadata', '1',
        *extra_args,
        '-ss', str(start_time),
        '-to', str(end_time),
        str(output_file),
    ]

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    finally:
        metadata_temp_file.close()


def sanitize_filename(filename):
    valid_filename_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    source = ''.join(c for c in filename if c in valid_filename_chars)
    source = source.replace("/", "-")
    return source


def prepare_chapters_whitelist(only_chapters, chapters_total_count):
    chapters_ranges = []
    for chapters_range in str(only_chapters).split(','):
        chapters_range = chapters_range.strip()

        if chapters_range.isnumeric():
            chapters_ranges.append(int(chapters_range))
            continue

        range_match = re.match(r"^(\d+)-(\d+)$", chapters_range)
        if range_match is not None:
            chapters_ranges.append(tuple((int(range_match.group(1)), int(range_match.group(2)))))
            continue

        raise ValueError('Invalid chapters filter "{}"'.format(chapters_range))

    for chapters_range in chapters_ranges:
        if type(chapters_range) is tuple:
            if (
                    chapters_range[0] < 1
                    or chapters_range[0] > chapters_total_count
                    or chapters_range[0] > chapters_range[1]
                    or chapters_range[1]
            ):
                raise ValueError('Chapters filter out of range "{}"'.format(str(chapters_range)))
        else:
            if chapters_range < 1 or chapters_range > chapters_total_count:
                raise ValueError('Chapters filter out of range "{}"'.format(str(chapters_range)))

    return chapters_ranges


def is_chapter_allowed(chapter, chapters_whitelist):
    if chapters_whitelist is None:
        return True

    chapter_number = chapter['number']
    for chapters_range in chapters_whitelist:
        if type(chapters_range) is tuple:
            return chapters_range[0] <= chapter_number <= chapters_range[1]
        return chapters_range == chapter_number


def process(options):
    input_file = os.path.abspath(os.path.expanduser(os.path.expandvars(options.input)))
    input_file_basename, input_file_extension = os.path.splitext(input_file)
    chapters = parse_chapters(input_file)

    print('Found chapters: {}'.format(len(chapters)))

    if options.dir is None:
        output_dir = os.path.join(os.getcwd(), input_file_basename)
    else:
        output_dir = os.path.abspath(os.path.expanduser(os.path.expandvars(options.dir)))

    try:
        os.mkdir(output_dir)
    except FileExistsError:
        if not options.overwrite:
            print(f"Output directory {output_dir} already exists, use -f option to force overwrite")
            sys.exit(1)
        else:
            pass

    if options.output_ext is None:
        output_file_extension = input_file_extension
    else:
        output_file_extension = '.' + options.output_ext

    chapters_to_be_processed = []
    if options.only_chapters:
        chapters_whitelist = prepare_chapters_whitelist(options.only_chapters, len(chapters))
        for chapter in chapters:
            if is_chapter_allowed(chapter, chapters_whitelist):
                chapters_to_be_processed.append(chapter)
    else:
        chapters_to_be_processed = chapters

    if not chapters_to_be_processed:
        raise ValueError('No chapters to be processed')

    processed_chapters_count = 1
    for chapter in chapters_to_be_processed:
        chapter_number_formatted = str(chapter['number']).rjust(len(str(len(chapters))), '0')
        file_name = chapter_number_formatted + ' - ' + str(chapter['title']) + output_file_extension
        output_file = os.path.join(output_dir, sanitize_filename(file_name))
        metadata = {
            "title": chapter['title'],
            "track": str(chapter['number']) + '/' + str(len(chapters))
        }
        if options.meta_artist:
            metadata["artist"] = options.meta_artist
            metadata["album_artist"] = options.meta_artist
            metadata["composer"] = options.meta_artist
        if options.meta_composer:
            metadata["composer"] = options.meta_composer
        if options.meta_album_artist:
            metadata["album_artist"] = options.meta_album_artist
        if options.meta_album:
            metadata["album"] = options.meta_album
        else:
            metadata["album"] = input_file_basename
        if options.meta_genre:
            metadata["genre"] = options.meta_genre
        if options.meta_date:
            metadata["date"] = options.meta_date

        print('Processing chapter {}/{}: {}'.format(processed_chapters_count, len(chapters_to_be_processed), file_name))
        convert_file(input_file, output_file, chapter['start'], chapter['end'], metadata, options.flags)
        processed_chapters_count += 1


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options] [FILE]...", version="%prog 1.0")
    parser.add_option("-f", "--force", action="store_true", dest="overwrite", help="Force overwrite")
    parser.add_option("-i", "--input", dest="input", help="Input file")
    parser.add_option("-d", "--dir", dest="dir", help="Output directory")
    parser.add_option('--flags', dest="flags", help="ffmpeg flags")
    parser.add_option('--output-ext', dest="output_ext", help="output extension override")
    parser.add_option('--only-chapters', dest="only_chapters", help="Only specified chapters will be processed")

    parser.add_option('--meta_artist', dest="meta_artist", help="Specify artist for metadata")
    parser.add_option('--meta_composer', dest="meta_composer", help="Specify composer for metadata")
    parser.add_option('--meta_album_artist', dest="meta_album_artist", help="Specify album_artist for metadata")
    parser.add_option('--meta_album', dest="meta_album", help="Specify album for metadata")
    parser.add_option('--meta_genre', dest="meta_genre", help="Specify genre for metadata")
    parser.add_option('--meta_date', dest="meta_date", help="Specify date for metadata")

    (options, args) = parser.parse_args()
    process(options)
