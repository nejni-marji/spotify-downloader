import asyncio
import subprocess
import sys
import re


def has_correct_version(
    skip_version_check: bool = False, ffmpeg_path: str = "ffmpeg"
) -> bool:
    try:
        process = subprocess.Popen(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
    except FileNotFoundError:
        print("FFmpeg was not found, spotDL cannot continue.", file=sys.stderr)
        return False

    output = "".join(process.communicate())

    # remove all non numeric characters from string example: n4.3
    if skip_version_check:
        return True

    result = re.search(r"ffmpeg version \w?(\d+\.)?(\d+)", output)

    # fallback to copyright date check
    if result is not None:
        version_str = result.group(0)

        # remove all non numeric characters from string example: n4.3
        version_str = re.sub(r"[a-zA-Z]", "", version_str)
        version = float(version_str)

        if version < 4.2:
            print(
                f"Your FFmpeg installation is too old ({version}), please update to 4.2+\n",
                file=sys.stderr,
            )
            return False

        return True
    else:
        # fallback to copyright date check
        date_result = re.search(r"Copyright \(c\) \d\d\d\d\-202\d", output)

        if date_result is not None:
            return True

        print("Your FFmpeg version couldn't be detected", file=sys.stderr)
        return False


async def convert(
    downloaded_file_path, converted_file_path, ffmpeg_path, output_format
) -> bool:
    # ! '-abr true' automatically determines and passes the
    # ! audio encoding bitrate to the filters and encoder. This ensures that the
    # ! sampled length of songs matches the actual length (i.e. a 5 min song won't display
    # ! as 47 seconds long in your music player, yeah that was an issue earlier.)

    downloaded_file_path = str(downloaded_file_path.absolute())
    converted_file_path = str(converted_file_path.absolute())

    formats = {
        "mp3": ["-codec:a", "libmp3lame"],
        "flac": ["-codec:a", "flac"],
        "ogg": ["-codec:a", "libvorbis"],
        "opus": ["-vn", "-c:a", "copy"]
        if downloaded_file_path.endswith(".opus")
        else ["-c:a", "libopus"],
        "m4a": ["-codec:a", "aac", "-vn"],
        "wav": [],
    }

    if output_format is None:
        output_format_command = formats["mp3"]
    else:
        output_format_command = formats[output_format]

    #! Different audio codecs use the "quality" setting differently.
    #!
    #! For mp3: 0 is the highest quality, and 9 is the lowest.
    #! For vorbis: 0 is the lowest quality, and 10 is the highest.
    #!
    #! By default, vorbis uses 3, which is fine when ripping a CD, but not good for
    #! transcoding from a lossy format. I have found that using 5 works well to mitigate
    #! compound losses from lossy-to-lossy transcodes without taking up too much space.
    #!
    #! Also, about m4a, aka AAC... I can't find any strict documentation for how it uses
    #! the "quality" setting. By default, it wants to use 128 kb/s rather than any quality
    #! setting, and personally, I don't see any reason to change that. For later
    #! reference, 128 kb/s lies somewhere between quality 1 and 2.
    #!
    #! For all other codecs, 0 is interpreted as a null/default value, which I believe to
    #! be acceptable.

    if output_format == "ogg":
        output_quality_command = ["-q:a", "5"]
    elif output_format == "m4a":
        output_quality_command = []
    else:
        output_quality_command = ["-q:a", "0"]

    if ffmpeg_path is None:
        ffmpeg_path = "ffmpeg"

    arguments = [  # type: ignore
        "-i",
        downloaded_file_path,
        *output_format_command,
        "-abr",
        "true",
        *output_quality_command,
        "-v",
        "debug",
        converted_file_path,
    ]

    process = await asyncio.subprocess.create_subprocess_exec(
        ffmpeg_path,
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    proc_out = await process.communicate()

    if proc_out[0] or proc_out[1]:
        out = str(b"".join(proc_out))
    else:
        out = ""

    if process.returncode != 0:
        message = (
            f"ffmpeg returned an error ({process.returncode})"
            f'\nffmpeg arguments: "{" ".join(arguments)}"'
            "\nffmpeg gave this output:"
            "\n=====\n"
            f"{out}"
            "\n=====\n"
        )

        print(message, file=sys.stderr)
        return False

    return True
