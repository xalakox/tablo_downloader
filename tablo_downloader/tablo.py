#!/usr/bin/env python3

import argparse
import json
import logging
import os
import pprint
import subprocess
import tempfile

from tablo_downloader import apis
from tablo_downloader.validation import validate_video_file, validate_video_file_detailed

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
HANDLER = logging.StreamHandler()
HANDLER.setFormatter(
    logging.Formatter(
        '%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s'))
LOGGER.addHandler(HANDLER)

SETTINGS_FILE = '.tablodlrc'
DATABASE_FILE = '.tablodldb'


def load_settings():
    """Load settings from JSON file /home_directory/{SETTINGS_FILE}."""
    settings = {}
    sfile = os.path.join(os.path.expanduser("~"), SETTINGS_FILE)
    if os.path.exists(sfile) and os.path.getsize(sfile) > 0:
        LOGGER.debug('Loading settings from [%s]', sfile)
        with open(sfile) as f:
            settings = json.load(f)
    return settings


def load_recordings_db(rfile):
    recordings = {}
    if os.path.exists(rfile) and os.path.getsize(rfile) > 0:
        with open(rfile) as f:
            recordings = json.load(f)
    return recordings


def save_recordings_db(recordings, recordings_file):
    # Ensure the directory exists
    directory = os.path.dirname(recordings_file)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        
    with open(recordings_file, 'w') as f:
        f.write(json.dumps(recordings))


def local_ips():
    """Get a list of IPs of local Tablo servers."""
    info = apis.local_server_info()
    LOGGER.debug('Local server info [%s]', info)
    ips = {cpe['private_ip'] for cpe in info['cpes']}
    return ips


def recording_metadata(ip, recording):
    """Return metadata for a recording."""
    res = {}
    res['category'] = recording.split('/')[2]
    res['details'] = apis.recording_details(ip, recording)
    return res


def recording_summary(metadata):
    dtls = metadata['details']
    res = {
        'category': metadata['category'],
        'episode_date': None,
        'episode_description': None,
        'episode_number': None,
        'episode_season': None,
        'episode_title': None,
        'event_description': None,
        'event_season': None,
        'event_title': None,
        'movie_year': None,
        'path': dtls.get('path'),
        'show_time': dtls.get('airing_details', {}).get('datetime'),
        'show_title': dtls.get('airing_details', {}).get('show_title'),
    }
    if metadata['category'] == 'movies':
        res['movie_year'] = dtls.get('movie_airing', {}).get('release_year')
    elif metadata['category'] == 'series':
        res['episode_title'] = dtls.get('episode', {}).get('title')
        res['episode_date'] = dtls.get('episode', {}).get('orig_air_date')
        res['episode_description'] = dtls.get('episode', {}).get('description')
        res['episode_season'] = dtls.get('episode', {}).get('season_number')
        res['episode_number'] = dtls.get('episode', {}).get('number')
    elif metadata['category'] == 'sports':
        res['event_title'] = dtls.get('event', {}).get('title')
        res['event_description'] = dtls.get('event', {}).get('description')
        res['event_season'] = dtls.get('event', {}).get('season')
    return res


def title_and_filename(summary):
    show_title = summary['show_title']
    if not show_title:
        show_title = 'UNKNOWN'  # TODO: Give better default?
    filename, title = show_title, show_title
    if summary['category'] == 'movies':
        year = summary['movie_year']
        if isinstance(year, int):
            filename += f' ({year})'
    elif summary['category'] == 'series':
        episode_title = summary['episode_title']
        if episode_title:
            filename += f'_-_{episode_title}'
            title += f' - {episode_title}'

        season = summary['episode_season']
        if isinstance(season, int) and season > 0:
            season = '%02d' % int(season)
        number = summary['episode_number']
        if isinstance(number, int) and number > 0:
            number = '%02d' % int(number)
            if not season:
                season = '00'
        if season:
            filename += f'_-_S{season}E{number}'
            if not episode_title:
                title += f' - S{season}E{number}'

        if not episode_title and not season:
            filename += ' %s' % summary['show_time'][:10]

    elif summary['category'] == 'sports':
        event_title = summary['event_title']
        if event_title:
            filename += f'_-_{event_title}'
            title += f' - {event_title}'
        show_time = summary['show_time']
        if show_time:
            filename += f'_-_{show_time[:10]}'
            title += f' - {show_time[:10]}'
    else:
        return None, None
    filename = ('%s.mp4' % filename).replace(' ', '_')
    return title, filename


def find_recording_by_show_title(recordings, ip, show_title):
    """Find the most recent recording that partially matches the given show title."""
    if not recordings or not ip in recordings or not show_title:
        return None, None
    
    matching_recordings = []
    
    for rec_id, rec_data in recordings[ip].items():
        summary = recording_summary(rec_data)
        title, _ = title_and_filename(summary)
        
        if title and show_title.lower() in title.lower():
            # Add to matching recordings with timestamp for sorting
            show_time = summary.get('show_time')
            if show_time:
                matching_recordings.append((rec_id, show_time, rec_data))
    
    # Sort by show_time in descending order (most recent first)
    matching_recordings.sort(key=lambda x: x[1], reverse=True)
    
    if matching_recordings:
        # Return the most recent matching recording ID and its data
        return matching_recordings[0][0], matching_recordings[0][2]
    
    return None, None


def validate_existing_downloads(args):
    """Validate all existing downloaded files in the recordings directory."""
    recordings_dir = args.recordings_directory
    if not recordings_dir or not os.path.exists(recordings_dir):
        LOGGER.error('Recordings directory does not exist: %s', recordings_dir)
        return

    results = {'valid': 0, 'invalid': 0, 'errors': 0}

    for filename in sorted(os.listdir(recordings_dir)):
        if not filename.endswith('.mp4'):
            continue

        filepath = os.path.join(recordings_dir, filename)
        try:
            is_valid, reason = validate_video_file(filepath)
            if is_valid:
                results['valid'] += 1
                LOGGER.info('VALID: %s - %s', filename, reason)
            else:
                results['invalid'] += 1
                LOGGER.warning('INVALID: %s - %s', filename, reason)
        except Exception as e:
            results['errors'] += 1
            LOGGER.error('ERROR validating %s: %s', filename, e)

    print(f"\n=== Validation Summary ===")
    print(f"Valid: {results['valid']}")
    print(f"Invalid: {results['invalid']}")
    print(f"Errors: {results['errors']}")


def download_recording(args):
    ip = args.tablo_ips.split(',')[0]
    recording_id = args.recording_id
    
    recordings = load_recordings_db(args.database_folder)
    if not recordings:
        LOGGER.error('No recordings database. Run with --updatedb to create.')
        return
    
    recording = None
    
    # If --show argument is provided, find the matching recording
    if args.show and not recording_id:
        LOGGER.info('Searching for most recent recording matching: %s', args.show)
        recording_id, recording = find_recording_by_show_title(recordings, ip, args.show)
        if not recording_id:
            LOGGER.error('No recordings found matching show title: %s', args.show)
            return
        LOGGER.info('Found matching recording: %s', recording_id)
    else:
        recording = recordings.get(ip, {}).get(recording_id)
        if not recording:
            LOGGER.error(
                    'Recording [%s] on device [%s] not found', recording_id, ip)
            return

    playlist = apis.playlist_info(ip, recording_id)
    if playlist.get('error'):
        LOGGER.error('Recording [%s] on device [%s] failed', recording_id, ip)
        return

    # Get expected duration from recording metadata for validation
    expected_duration = recording.get('details', {}).get('video_details', {}).get('duration')
    if expected_duration:
        LOGGER.debug('Expected recording duration: %s seconds', expected_duration)

    title, filename = title_and_filename(recording_summary(recording))
    if not title:
        LOGGER.error('Unable to generate title for recording [%s] on '
                     'device [%s]', ip, recording_id)
        return

    mp4_filename = os.path.join(args.recordings_directory, filename)
    if args.dry_run:
        if os.path.exists(mp4_filename):
            if args.overwrite:
                LOGGER.info('Dry run - Would overwrite existing download [%s]',
                            mp4_filename)
            else:
                LOGGER.info('Dry run - Would skip existing download [%s]',
                            mp4_filename)
        if args.delete_originals_after_downloading:
            LOGGER.info('Dry run - Would delete Tablo recording after '
                        'successful download of [%s]', mp4_filename)
        return

    if os.path.exists(mp4_filename):
        if args.overwrite:
            os.remove(mp4_filename)
            LOGGER.info('Removed existing file for re-download: %s', mp4_filename)
        else:
            # Validate existing file before skipping
            validation = validate_video_file_detailed(
                mp4_filename,
                expected_duration=expected_duration
            )

            if not validation['is_valid']:
                # File is corrupted or too small - delete and re-download
                LOGGER.warning('Existing download is corrupted: %s - %s',
                               mp4_filename, validation['reason'])
                os.remove(mp4_filename)
                LOGGER.info('Removed corrupted file for re-download')
            elif validation['deviation'] is None or validation['deviation'] <= 0.10:
                # No expected duration or within 10% tolerance - keep file
                LOGGER.info('Existing download is valid, skipping: %s - %s',
                            mp4_filename, validation['reason'])
                return
            elif validation['deviation'] > 0.50:
                # More than 50% deviation - clearly incomplete, auto-delete
                LOGGER.warning('Existing download is incomplete (>50%% deviation): %s - %s',
                               mp4_filename, validation['reason'])
                os.remove(mp4_filename)
                LOGGER.info('Removed incomplete file for re-download')
            else:
                # 10-50% deviation - ask user (might be different episode)
                LOGGER.warning('Existing file has duration mismatch: %s', validation['reason'])
                print(f"\nFile exists: {mp4_filename}")
                print(f"  Actual duration:   {validation['actual_duration']:.1f}s")
                print(f"  Expected duration: {validation['expected_duration']:.1f}s")
                print(f"  Deviation: {validation['deviation']:.1%}")
                print("\nThis could be a different episode or an incomplete download.")
                response = input("Delete and re-download? [y/N]: ").strip().lower()
                if response == 'y':
                    os.remove(mp4_filename)
                    LOGGER.info('Removed file for re-download per user request')
                else:
                    LOGGER.info('Keeping existing file per user request')
                    return

    m3u_data = apis.playlist_m3u(playlist)
    if not isinstance(m3u_data, str):  # Some error occurred.
        LOGGER.error(m3u_data)
        return

    m3u_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.m3u')
    m3u_filename = m3u_file.name
    m3u_file.write(m3u_data)
    m3u_file.close()

    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'warning',
        '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
        '-i', m3u_filename,
        '-c', 'copy',
        '-metadata', f'title={title}',
        mp4_filename
    ]
    LOGGER.debug('Running [%s]', ' '.join(cmd))

    status = subprocess.run(cmd)
    os.remove(m3u_filename)

    if status.returncode == 0:
        # Validate the downloaded file
        is_valid, reason = validate_video_file(
            mp4_filename,
            expected_duration=expected_duration
        )
        if is_valid:
            LOGGER.info('Successfully Downloaded and Validated [%s] - %s',
                        mp4_filename, reason)
            if args.delete_originals_after_downloading:
                LOGGER.info('Deleting Tablo recording [%s] on device [%s]',
                            recording_id, ip)
                apis.delete_recording(ip, recording_id)
        else:
            LOGGER.error('Download completed but validation failed: %s - %s',
                         mp4_filename, reason)
            os.remove(mp4_filename)
            LOGGER.info('Removed invalid download')
    else:
        LOGGER.error('FFmpeg failed with return code %d for [%s]',
                     status.returncode, mp4_filename)
        # Clean up partial file if it exists
        if os.path.exists(mp4_filename):
            os.remove(mp4_filename)
            LOGGER.info('Removed partial download after FFmpeg failure')


def create_or_update_recordings_database(args):
    recordings_by_ip = load_recordings_db(args.database_folder)
    tablo_ips = {ip for ip in recordings_by_ip}
    if args.tablo_ips:
        tablo_ips |= {x for x in args.tablo_ips.split(',') if x}
    elif tablo_ips:
        tablo_ips |= local_ips()
    LOGGER.info('Creating/Updating recording database for Tablo IPs [%s]',
                ' '.join(tablo_ips))

    for ip in tablo_ips:
        LOGGER.info('Getting recordings for IP [%s]', ip)
        if ip not in recordings_by_ip:
            recordings_by_ip[ip] = {}
        server_recordings = apis.server_recordings(ip)
        # Remove any items no longer present on the Tablo device.
        obsolete_db_recordings = {
                r for r in recordings_by_ip[ip] if r not in server_recordings}
        for recording in obsolete_db_recordings:
            LOGGER.debug('Removing deleted recording [%s %s]', ip, recording)
            del recordings_by_ip[ip][recording]
        # Add new recordings.
        for recording in server_recordings:
            if recording not in recordings_by_ip[ip]:
                LOGGER.info('Getting metadata for new recording [%s]', recording)
                recordings_by_ip[ip][recording] = recording_metadata(
                    ip, recording)
    save_recordings_db(recordings_by_ip, args.database_folder)


def truncate_string(s, length):
    if len(s) < length:
        return s
    sp = s[:length - 4].rfind(' ')
    return s[:sp] + ' ...'


def dump_recordings(recordings):
    summaries = {ip: {} for ip in recordings}
    for ip, recs in recordings.items():
        summaries[ip] = {r: recording_summary(recs[r]) for r in recs}
    for ip in sorted(summaries):
        for smry in sorted(summaries[ip].values(),
                           key=lambda k: (k['show_title'],
                                          k['episode_season'],
                                          k['episode_number'],
                                          k['show_time'])):
            titletag, filename = title_and_filename(smry)
            print('Filename : %s' % filename)
            print('Title Tag: %s' % titletag)

            if smry['episode_description']:
                print('Desc:      %s' % truncate_string(smry['episode_description'], 70))
            if smry['event_description']:
                print('Desc:      %s' % truncate_string(smry['event_description'], 70))
            print('Path:      %s' % smry['path'])
            print()


def parse_args_and_settings():
    parser = argparse.ArgumentParser(
        description='Manage recordings Tablo devices.')
    parser.add_argument(
        '--log_level',
        default='info',
        help='More verbose logging',
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Equivalent to --log_level=debug',
    )
    parser.add_argument(
        '--local_ips',
        action='store_true',
        help='Display the IPs of Tablo devices on a local network')
    parser.add_argument(
        '--tablo_ips',
        '--ips',
        '--ip',
        help='One or more IPs of Tablo device(s) separated by commas',
    )
    parser.add_argument(
        '--recording_id',
        help='A Tablo recording ID',
    )
    parser.add_argument(
        '--show',
        help='Download the most recent recording that partially matches this show title',
    )
    parser.add_argument(
        '--recordings_directory',
        help='A directory to store Tablo recordings',
    )
    parser.add_argument(
        '--updatedb',
        action='store_true',
        help='Create/Update Tablo recordings DB.',
    )
    parser.add_argument(
        '--dump',
        action='store_true',
        help='Dump Tablo recordings DB.',
    )
    parser.add_argument(
        '--recording_details',
        action='store_true',
        help='Display details of a Tablo recording.',
    )
    parser.add_argument(
        '--download_recording',
        '--download',
        action='store_true',
        help='Download a Tablo recording.',
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Display what would be done without updating anything.',
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing downloads.',
    )
    parser.add_argument(
        '--delete_originals_after_downloading',
        action='store_true',
        help='Delete Tablo recordings after successfully downloading them',
    )
    parser.add_argument(
        '--database_folder',
        default=os.path.join(os.path.expanduser("~"), DATABASE_FILE),
        help='Folder where the recordings database is stored. Defaults to home directory.',
    )
    parser.add_argument(
        '--validate_existing',
        action='store_true',
        help='Validate existing downloaded files and report their status.',
    )
    args = parser.parse_args()
    args_dict = vars(args)
    settings = load_settings()
    for setting in settings:
        if setting in args_dict:
            args_dict[setting] = settings[setting]
    return args


def main():
    args = parse_args_and_settings()
    if args.dry_run or args.verbose:
        vars(args)['log_level'] = 'debug'
    LOGGER.setLevel(getattr(logging, args.log_level.upper()))
    LOGGER.debug('Log level [%s]', args.log_level)

    if args.local_ips:
        print(','.join(local_ips()))

    if args.updatedb:
        create_or_update_recordings_database(args)

    if args.recording_details:
        pprint.pprint(apis.recording_details(
                recording_id=args.recording_id, ip=args.tablo_ips))

    if args.dump:
        recordings = load_recordings_db(args.database_folder)
        dump_recordings(recordings)

    if args.validate_existing:
        validate_existing_downloads(args)
        return

    if args.download_recording:
        download_recording(args)
        return
    
    if args.show:
        recordings = load_recordings_db(args.database_folder)
        (matched_id, recording_match) = find_recording_by_show_title(
           recordings, args.tablo_ips, args.show 
        )
        if (not matched_id):
            LOGGER.error('No recordings found matching show title: %s', args.show)
            return
        LOGGER.info('Found matching recording: %s', matched_id)
        args.recording_id = matched_id
        download_recording(args)

if __name__ == '__main__':
    main()
