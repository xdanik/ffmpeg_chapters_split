#!/usr/bin/env python3

import os
import re
import string
import sys
import tempfile
import subprocess
from optparse import OptionParser
import shlex
import glob

def convert_file(input_file, output_file, metadata, extra_flags):
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


def parse_episode_name(filename):
    basename = os.path.basename(filename)
    matches = re.search(r'^(.*) S(\d+)E(\d+)(?:-\d+)? (.*)$', os.path.splitext(basename)[0])
    return {
        'show': matches.group(1).rstrip(' -'),
        'season' : int(matches.group(2)),
        'episode' : int(matches.group(3)),
        'title' : matches.group(4).lstrip(' -'),
    }


def process(options):
    input_dir = os.path.abspath(os.path.expanduser(os.path.expandvars(options.input)))

    if options.dir is None:
        output_dir_root = os.path.abspath(os.getcwd())
    else:
        output_dir_root = os.path.abspath(os.path.expanduser(os.path.expandvars(options.dir)))


    max_season_episode = {}
    files_to_be_processed = []
    files = glob.glob(input_dir + "/**/**")
    for file in files:
        relative_path = os.path.relpath(file, input_dir)
        input_file_basename, input_file_extension = os.path.splitext(os.path.basename(file))
        if options.output_ext is None:
            output_file_extension = input_file_extension
        else:
            output_file_extension = '.' + options.output_ext

        output_dir = os.path.join(output_dir_root, os.path.split(relative_path)[0])
        output_path = os.path.join(output_dir, input_file_basename + output_file_extension)

        meta = parse_episode_name(file)
        files_to_be_processed.append({
            'input_path': file,
            'output_dir': output_dir,
            'output_path': output_path,
            'meta': meta,
        })
        if meta['season'] not in max_season_episode:
            max_season_episode[meta['season']] = 1
        max_season_episode[meta['season']] = max(max_season_episode[meta['season']], meta['episode'])

    if not files_to_be_processed:
        raise ValueError('No files found in the input dir')

    try:
        os.mkdir(output_dir_root)
    except FileExistsError:
        if not options.overwrite:
            print(f"Output directory {output_dir_root} already exists, use -f option to force overwrite")
            sys.exit(1)
        else:
            pass


    print('Found {} files'.format(len(files_to_be_processed)))

    files_to_be_processed = sorted(files_to_be_processed, key=lambda d: d['input_path'])

    processed_files_count = 1
    for file in files_to_be_processed:
        output_file = file['output_path']
        metadata = {
            "title": file['meta']['title'],
            "track": str(file['meta']['episode']) + '/' + str(max_season_episode[file['meta']['season']]),
            "artist": file['meta']['show'],
            "album_artist": file['meta']['show'],
            "composer": file['meta']['show'],
            "album": 'Season ' + str(file['meta']['season']).rjust(len(str(len(max_season_episode))), '0'),
        }
        if options.meta_genre:
            metadata["genre"] = options.meta_genre
        if options.meta_date:
            metadata["date"] = options.meta_date

        print('Processing chapter {}/{}: {}'.format(processed_files_count, len(files_to_be_processed), os.path.basename(output_file)))
        os.makedirs(file['output_dir'], exist_ok=True)
        convert_file(file['input_path'], output_file, metadata, options.flags)
        processed_files_count += 1


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options] [FILE]...", version="%prog 1.0")
    parser.add_option("-f", "--force", action="store_true", dest="overwrite", help="Force overwrite")
    parser.add_option("-i", "--input", dest="input", help="Input file")
    parser.add_option("-d", "--dir", dest="dir", help="Output directory")
    parser.add_option('--flags', dest="flags", help="ffmpeg flags")
    parser.add_option('--output-ext', dest="output_ext", help="output extension override")

    parser.add_option('--meta_genre', dest="meta_genre", help="Specify genre for metadata")
    parser.add_option('--meta_date', dest="meta_date", help="Specify date for metadata")

    (options, args) = parser.parse_args()
    process(options)
