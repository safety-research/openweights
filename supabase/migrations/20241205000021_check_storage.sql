-- Check storage objects
select id, bucket_id, name 
from storage.objects 
where name like '%14e5eef3bbad%'
or name like '%organizations%'
order by name;