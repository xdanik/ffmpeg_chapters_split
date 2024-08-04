# ffmpeg_split

Split video file to separate video files by chapters

## Motivation
Prepare concert videos for Volkswagen MIB3 entertainment unit witch is able to play videos but lacks chapters support.
Using this script I am able to split each chapter to separate file and also include the chapter name as a movie title.

## Usage
```
# basic usage
python3 split_ffmpeg.py -i input_file -d output_directory
# advanced usage with encoding
python3 split_ffmpeg.py --input input_file -f --flags="-c:v libx264 -crf 18 -c:a aac -b:a 320k" --meta_artist "Artis" --output-ext mp4 -d output_dir --only-chapters "1-3"
```

## Used commands for VW MIB3 (notes to myself)
```
# basic
python3 split_ffmpeg.py --input input -f --flags="-map 0:v:0 -map 0:a:0 -vf scale=-1:min\'(720,ih)\':force_original_aspect_ratio=decrease,format=yuv420p -c:v libx264 -profile:v high -preset slower -crf 18 -c:a aac -b:a 320k" --meta_artist "..." --meta_album "..." --meta_date=2000 --output-ext mp4 -d output_dir

# HDR10 to SDR
python3 split_ffmpeg.py --input input -f --flags="-map 0:v:0 -map 0:a:0 -vf scale=-1:min\'(720,ih)\':force_original_aspect_ratio=decrease,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p -c:v libx264 -profile:v high -preset slower -crf 18 -ac 2 -c:a aac -b:a 320k" --meta_artist "..." --meta_album "..." --meta_date=2000 --output-ext mp4 -d output_dir
```
