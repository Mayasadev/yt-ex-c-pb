import re
import json
import time
import pytz
import pandas as pd
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
api_key = "api key kamu"
youtube = build('youtube', 'v3', developerKey=api_key)

def get_comment(video_id, max_c):
    comments = []
    next_page_token = None
    while len(comments) < max_c:
        try:
            request = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=min(100, max_c - len(comments)),
                pageToken=next_page_token,
                order='relevance',
                textFormat='plainText'
            )
            response = request.execute()
        except HttpError as e:
            print(f" [!] Error komentar: {e}")
            break

        for item in response.get('items', []):
            snippet = item['snippet']['topLevelComment']['snippet']
            pub_utc = datetime.strptime(
                snippet['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'
            ).replace(tzinfo=pytz.utc)

            comments.append({
                'video_id': video_id,
                'username': snippet.get('authorDisplayName', 'Anonim'),
                'komentar_id': item['id'],
                'comment': snippet.get('textDisplay', '').replace('\n', ' '),
                'like_count': snippet.get('likeCount', 0),
                'reply_count': item['snippet'].get('totalReplyCount', 0),
                'published': pub_utc.strftime('%Y-%m-%d %H:%M:%S')
            })
            if len(comments) >= max_c:
                break

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    return comments

def get_video(rc, max_v):
    videos = []
    next_page_token = None
    while len(videos) < max_v:
        try:
            request = youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=rc,
                maxResults=min(50, max_v - len(videos)),
                pageToken=next_page_token
            )
            respon = request.execute()
        except HttpError as e:
            print(f" [!] Error video: {e}")
            break

        for item in respon.get('items', []):
            snippet = item['snippet']
            stats = item['statistics']
            videos.append({
                'video_id': item['id'],
                'judul': snippet.get('title', ''),
                'channel': snippet.get('channelTitle', ''),
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'published': snippet.get('publishedAt', '')
            })
        next_page_token = respon.get('nextPageToken')
        if not next_page_token:
            break
    return videos

def create_parquet(df_komen, df_video, kode_negara):
    df_komen_only = df_komen.copy()
    df_komen_only['kode_negara'] = kode_negara
    df_komen_only['waktu_upload_komen'] = pd.to_datetime(df_komen_only['published'], errors='coerce')

    df_komen_only = df_komen_only.rename(columns={
        'username': 'username_komentar',
        'komentar_id': 'id_komentar',
        'comment': 'komentar',
        'like_count': 'jumlah_like_komentar',
        'reply_count': 'jumlah_reply_komentar'
    })

    filename_komen = f"komentar_{kode_negara}.parquet"
    df_komen_only.to_parquet(filename_komen, index=False, engine='pyarrow')
    print(f"Saved komentar: {filename_komen} | Baris: {len(df_komen_only)}")
    df_final = df_komen.merge(df_video, on='video_id', how='left')
    df_final['kode_negara'] = kode_negara

    df_final['waktu_upload_komen'] = pd.to_datetime(df_final['published_x'], errors='coerce')
    df_final['waktu_upload_video'] = pd.to_datetime(df_final['published_y'], errors='coerce')

    df_final = df_final.rename(columns={
        'channel': 'nama_channel_video',
        'judul': 'judul_video',
        'views': 'views_video',
        'likes': 'likes_video',
        'username': 'username_komentar',
        'komentar_id': 'id_komentar',
        'comment': 'komentar',
        'like_count': 'jumlah_like_komentar',
        'reply_count': 'jumlah_reply_komentar'
    })

    df_final = df_final[[
        'kode_negara','nama_channel_video', 'video_id', 'waktu_upload_video', 'judul_video',
        'views_video', 'likes_video', 'username_komentar', 'id_komentar',
        'komentar', 'jumlah_like_komentar', 'jumlah_reply_komentar',
        'waktu_upload_komen'
    ]]

    filename_gabungan = f"{kode_negara}.parquet"
    df_final.to_parquet(filename_gabungan, index=False, engine='pyarrow')
    print(f"Saved gabungan: {filename_gabungan} | Baris: {len(df_final)}")

    return filename_komen, filename_gabungan


def ambil_data():
    try:
        with open('kode_negara.json', 'r') as kn:
            knn = json.load(kn)
        target = knn['kode_negara'][0]
    except:
        print("kode negara sudah tidak ada")
        return

    print(f"Mulai: {target}")
    all_comments = []
    all_videos = []

    data_video = get_video(rc=target, max_v=10 ** 100)
    all_videos.extend(data_video)

    for i, item in enumerate(data_video):
        vid = item['video_id']
        print(f"[{i+1}/{len(data_video)}] {vid}")
        try:
            comments = get_comment(video_id=vid, max_c=10 ** 100) 
            all_comments.extend(comments)
        except HttpError as e:
            if 'quotaExceeded' in str(e):
                print("KUOTA HABIS")
                break
            continue
        time.sleep(0.1)

    if all_comments and all_videos:
        df_komen = pd.DataFrame(all_comments)
        df_video = pd.DataFrame(all_videos)
        create_parquet(df_komen, df_video, target)

def main():
    try:
        ambil_data() 
    except FileNotFoundError as e:
        print(f"[ERROR] File tidak ketemu: {e}")
        print("Pastikan kode_negara.json ada di folder yang sama")

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON rusak: {e}")
        print("Cek isi kode_negara.json")

    except HttpError as e:
        if 'quotaExceeded' in str(e):
            print("[ERROR] Kuota YouTube API habis hari ini")
            print("coba lagi nanti")
        elif 'keyInvalid' in str(e):
            print("[ERROR] API Key salah")
        else:
            print(f"[ERROR] YouTube API: {e}")

    except MemoryError:
        print("[ERROR] RAM habis (Signal 9)")
        print("Kurangi max_v dan max_c di ambil_data()")

    except KeyboardInterrupt:
        print("\n[INFO] Dihentikan manual oleh user")

    except Exception as e:
        print(f"[ERROR TAK TERDUGA] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("Program keluar")

if __name__ == "__main__":
    main()