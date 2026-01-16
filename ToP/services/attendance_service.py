import base64
import uuid
from django.core.files.base import ContentFile
from django.utils import timezone
from ..models import AttendanceLog

class AttendanceActionService:
    @staticmethod
    def record_attendance(user, action, latitude, longitude, image_b64):
        format, imgstr = image_b64.split(';base64,') 
        ext = format.split('/')[-1] 
        file_name = f"{user.id}_{uuid.uuid4()}.{ext}"
        image_data = ContentFile(base64.b64decode(imgstr), name=file_name)

        AttendanceLog.objects.create(
            user=user,
            action=action,
            latitude=latitude,
            longitude=longitude,
            photo=image_data
        )

    @staticmethod
    def delete_logs(log_ids):
        """
        Deletes attendance records AND their associated image files from storage.
        """
        valid_ids = [x for x in log_ids if x and str(x).lower() != 'none']
        
        if not valid_ids:
            raise ValueError("No valid IDs provided.")

        # 1. Fetch the actual objects first
        logs_to_delete = AttendanceLog.objects.filter(id__in=valid_ids)
        
        count = 0
        for log in logs_to_delete:
            # 2. Delete the physical file if it exists
            if log.photo:
                try:
                    # save=False prevents auto-saving the model during file deletion
                    log.photo.delete(save=False) 
                except Exception:
                    pass # Continue even if file is missing from disk
            
            # 3. Delete the database record
            log.delete()
            count += 1
            
        return count

    @staticmethod
    def cleanup_old_images(days=30):
        """
        Deletes physical image files older than 'days' but keeps the logs.
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        # Find logs older than cutoff that HAVE a photo
        old_logs = AttendanceLog.objects.filter(timestamp__lt=cutoff_date).exclude(photo='')
        
        count = 0
        for log in old_logs:
            if log.photo:
                try:
                    log.photo.delete(save=False) # Delete file from OS/S3
                    log.photo = None             # Clear DB reference
                    log.save()
                    count += 1
                except Exception:
                    pass 
        return count


class AttendanceQueryService:
    @staticmethod
    def get_all_grouped_data():
        queryset = AttendanceLog.objects.select_related('user').all().order_by('timestamp')
        return AttendanceQueryService._group_logs_by_day(queryset)

    @staticmethod
    def _group_logs_by_day(queryset):
        grouped_data = {}

        for log in queryset:
            log_date = log.timestamp.date()
            date_str = log_date.strftime('%Y-%m-%d') 
            
            key = (log.user_id, date_str)

            if key not in grouped_data:
                grouped_data[key] = {
                    'user_name': log.user.full_name,
                    'user_role': log.user.role,
                    'date_obj': log_date, 
                    'date_str': log_date.strftime('%d/%m/%Y'), 
                    'filter_date': date_str, 
                    'check_in_lat': None,
                    'check_in_lng': None,
                    'check_out_lat': None,
                    'check_out_lng': None,
                    'check_in': None,
                    'check_out': None,
                    'check_in_id': None,
                    'check_out_id': None,
                    'check_in_photo': None,
                    'check_out_photo': None
                }

            lat = float(log.latitude) if log.latitude else 0.0
            lng = float(log.longitude) if log.longitude else 0.0

            if log.action == 'IN':
                if grouped_data[key]['check_in'] is None:
                    grouped_data[key]['check_in'] = log.timestamp.isoformat()
                    grouped_data[key]['check_in_id'] = log.id
                    grouped_data[key]['check_in_lat'] = lat
                    grouped_data[key]['check_in_lng'] = lng
                    if log.photo:
                        grouped_data[key]['check_in_photo'] = log.photo.url
            
            elif log.action == 'OUT':
                grouped_data[key]['check_out'] = log.timestamp.isoformat()
                grouped_data[key]['check_out_id'] = log.id
                grouped_data[key]['check_out_lat'] = lat
                grouped_data[key]['check_out_lng'] = lng
                if log.photo:
                    grouped_data[key]['check_out_photo'] = log.photo.url

        results = list(grouped_data.values())
        results.sort(key=lambda x: x['date_obj'], reverse=True)
        
        for r in results:
            del r['date_obj']
            
        return results