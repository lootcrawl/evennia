# Generated by Django 3.2.3 on 2021-05-30 18:18

from django.db import migrations

def update_help_entries(apps, schema_editor):
    """
    Change all help-entry files that use view: locks to read: locks
    (read: was not used before and view: was previously what read is now).

    """
    HelpEntry = apps.get_model("help", "HelpEntry")
    for help_entry in HelpEntry.objects.all():
        lock_storage = help_entry.db_lock_storage
        lock_storage = dict(lstring.split(":", 1) if ":" in lstring else (lstring, "")
                            for lstring in str(lock_storage).split(";"))
        if "read" in lock_storage:
            # already in place - skip
            continue
        if "view" in lock_storage:
            lock_storage["read"] = lock_storage.pop("view")
        lock_storage = ";".join(f"{typ}:{lock}" for typ, lock in lock_storage.items())
        help_entry.db_lock_storage = lock_storage
        help_entry.save(update_fields=["db_lock_storage"])


class Migration(migrations.Migration):

    dependencies = [
        ('help', '0004_auto_20210520_2137'),
    ]

    operations = [
        migrations.RunPython(update_help_entries)
    ]
