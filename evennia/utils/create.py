"""
This module gathers all the essential database-creation functions for the game
engine's various object types.

Only objects created 'stand-alone' are in here. E.g. object Attributes are
always created through their respective objects handlers.

Each `creation_*` function also has an alias named for the entity being created,
such as create_object() and object(). This is for consistency with the
utils.search module and allows you to do the shorter `create.object()`.

The respective object managers hold more methods for manipulating and searching
objects already existing in the database.

"""
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone
from evennia.utils import logger
from evennia.server import signals
from evennia.utils.utils import make_iter, class_from_module, dbid_to_obj

# delayed imports
_User = None
_ObjectDB = None
_Object = None
_Script = None
_ScriptDB = None
_HelpEntry = None
_Msg = None
_Account = None
_AccountDB = None
_to_object = None
_ChannelDB = None


# limit symbol import from API
__all__ = (
    "create_object",
    "create_script",
    "create_help_entry",
    "create_message",
    "create_channel",
    "create_account",
)

_GA = object.__getattribute__

#
# Game Object creation


def create_object(
    typeclass=None,
    key=None,
    location=None,
    home=None,
    permissions=None,
    locks=None,
    aliases=None,
    tags=None,
    destination=None,
    report_to=None,
    nohome=False,
    attributes=None,
    nattributes=None,
):
    """

    Create a new in-game object.

    Keyword Args:
        typeclass (class or str): Class or python path to a typeclass.
        key (str): Name of the new object. If not set, a name of
            `#dbref` will be set.
        location (Object or str): Obj or #dbref to use as the location of the new object.
        home (Object or str): Obj or #dbref to use as the object's home location.
        permissions (list): A list of permission strings or tuples (permstring, category).
        locks (str): one or more lockstrings, separated by semicolons.
        aliases (list): A list of alternative keys or tuples (aliasstring, category).
        tags (list): List of tag keys or tuples (tagkey, category) or (tagkey, category, data).
        destination (Object or str): Obj or #dbref to use as an Exit's target.
        report_to (Object): The object to return error messages to.
        nohome (bool): This allows the creation of objects without a
            default home location; only used when creating the default
            location itself or during unittests.
        attributes (list): Tuples on the form (key, value) or (key, value, category),
            (key, value, lockstring) or (key, value, lockstring, default_access).
            to set as Attributes on the new object.
        nattributes (list): Non-persistent tuples on the form (key, value). Note that
            adding this rarely makes sense since this data will not survive a reload.

    Returns:
        object (Object): A newly created object of the given typeclass.

    Raises:
        ObjectDB.DoesNotExist: If trying to create an Object with
            `location` or `home` that can't be found.

    """
    global _ObjectDB
    if not _ObjectDB:
        from evennia.objects.models import ObjectDB as _ObjectDB

    typeclass = typeclass if typeclass else settings.BASE_OBJECT_TYPECLASS

    # convenience converters to avoid common usage mistake
    permissions = make_iter(permissions) if permissions is not None else None
    locks = make_iter(locks) if locks is not None else None
    aliases = make_iter(aliases) if aliases is not None else None
    tags = make_iter(tags) if tags is not None else None
    attributes = make_iter(attributes) if attributes is not None else None

    if isinstance(typeclass, str):
        # a path is given. Load the actual typeclass
        typeclass = class_from_module(typeclass, settings.TYPECLASS_PATHS)

    # Setup input for the create command. We use ObjectDB as baseclass here
    # to give us maximum freedom (the typeclasses will load
    # correctly when each object is recovered).

    location = dbid_to_obj(location, _ObjectDB)
    destination = dbid_to_obj(destination, _ObjectDB)
    home = dbid_to_obj(home, _ObjectDB)
    if not home:
        try:
            home = dbid_to_obj(settings.DEFAULT_HOME, _ObjectDB) if not nohome else None
        except _ObjectDB.DoesNotExist:
            raise _ObjectDB.DoesNotExist(
                "settings.DEFAULT_HOME (= '%s') does not exist, or the setting is malformed."
                % settings.DEFAULT_HOME
            )

    # create new instance
    new_object = typeclass(
        db_key=key,
        db_location=location,
        db_destination=destination,
        db_home=home,
        db_typeclass_path=typeclass.path,
    )
    # store the call signature for the signal
    new_object._createdict = dict(
        key=key,
        location=location,
        destination=destination,
        home=home,
        typeclass=typeclass.path,
        permissions=permissions,
        locks=locks,
        aliases=aliases,
        tags=tags,
        report_to=report_to,
        nohome=nohome,
        attributes=attributes,
        nattributes=nattributes,
    )
    # this will trigger the save signal which in turn calls the
    # at_first_save hook on the typeclass, where the _createdict can be
    # used.
    new_object.save()

    signals.SIGNAL_OBJECT_POST_CREATE.send(sender=new_object)

    return new_object


# alias for create_object
object = create_object


#
# Script creation


def create_script(
    typeclass=None,
    key=None,
    obj=None,
    account=None,
    locks=None,
    interval=None,
    start_delay=None,
    repeats=None,
    persistent=None,
    autostart=True,
    report_to=None,
    desc=None,
    tags=None,
    attributes=None,
):
    """
    Create a new script. All scripts are a combination of a database
    object that communicates with the database, and an typeclass that
    'decorates' the database object into being different types of
    scripts.  It's behaviour is similar to the game objects except
    scripts has a time component and are more limited in scope.

    Keyword Args:
        typeclass (class or str): Class or python path to a typeclass.
        key (str): Name of the new object. If not set, a name of
            #dbref will be set.
        obj (Object): The entity on which this Script sits. If this
            is `None`, we are creating a "global" script.
        account (Account): The account on which this Script sits. It is
            exclusiv to `obj`.
        locks (str): one or more lockstrings, separated by semicolons.
        interval (int): The triggering interval for this Script, in
            seconds. If unset, the Script will not have a timing
            component.
        start_delay (bool): If `True`, will wait `interval` seconds
            before triggering the first time.
        repeats (int): The number of times to trigger before stopping.
            If unset, will repeat indefinitely.
        persistent (bool): If this Script survives a server shutdown
            or not (all Scripts will survive a reload).
        autostart (bool): If this Script will start immediately when
            created or if the `start` method must be called explicitly.
        report_to (Object): The object to return error messages to.
        desc (str): Optional description of script
        tags (list): List of tags or tuples (tag, category).
        attributes (list): List if tuples (key, value) or (key, value, category)
           (key, value, lockstring) or (key, value, lockstring, default_access).

    Returns:
        script (obj): An instance of the script created

    See evennia.scripts.manager for methods to manipulate existing
    scripts in the database.

    """
    global _ScriptDB
    if not _ScriptDB:
        from evennia.scripts.models import ScriptDB as _ScriptDB

    typeclass = typeclass if typeclass else settings.BASE_SCRIPT_TYPECLASS

    if isinstance(typeclass, str):
        # a path is given. Load the actual typeclass
        typeclass = class_from_module(typeclass, settings.TYPECLASS_PATHS)

    # validate input
    kwarg = {}
    if key:
        kwarg["db_key"] = key
    if account:
        kwarg["db_account"] = dbid_to_obj(account, _AccountDB)
    if obj:
        kwarg["db_obj"] = dbid_to_obj(obj, _ObjectDB)
    if interval:
        kwarg["db_interval"] = max(0, interval)
    if start_delay:
        kwarg["db_start_delay"] = start_delay
    if repeats:
        kwarg["db_repeats"] = max(0, repeats)
    if persistent:
        kwarg["db_persistent"] = persistent
    if desc:
        kwarg["db_desc"] = desc
    tags = make_iter(tags) if tags is not None else None
    attributes = make_iter(attributes) if attributes is not None else None

    # create new instance
    new_script = typeclass(**kwarg)

    # store the call signature for the signal
    new_script._createdict = dict(
        key=key,
        obj=obj,
        account=account,
        locks=locks,
        interval=interval,
        start_delay=start_delay,
        repeats=repeats,
        persistent=persistent,
        autostart=autostart,
        report_to=report_to,
        desc=desc,
        tags=tags,
        attributes=attributes,
    )
    # this will trigger the save signal which in turn calls the
    # at_first_save hook on the typeclass, where the _createdict
    # can be used.
    new_script.save()

    if not new_script.id:
        # this happens in the case of having a repeating script with `repeats=1` and
        # `start_delay=False` - the script will run once and immediately stop before save is over.
        return None

    signals.SIGNAL_SCRIPT_POST_CREATE.send(sender=new_script)

    return new_script


# alias
script = create_script


#
# Help entry creation
#


def create_help_entry(key, entrytext, category="General", locks=None, aliases=None, tags=None):
    """
    Create a static help entry in the help database. Note that Command
    help entries are dynamic and directly taken from the __doc__
    entries of the command. The database-stored help entries are
    intended for more general help on the game, more extensive info,
    in-game setting information and so on.

    Args:
        key (str): The name of the help entry.
        entrytext (str): The body of te help entry
        category (str, optional): The help category of the entry.
        locks (str, optional): A lockstring to restrict access.
        aliases (list of str, optional): List of alternative (likely shorter) keynames.
        tags (lst, optional): List of tags or tuples `(tag, category)`.

    Returns:
        help (HelpEntry): A newly created help entry.

    """
    global _HelpEntry
    if not _HelpEntry:
        from evennia.help.models import HelpEntry as _HelpEntry

    try:
        new_help = _HelpEntry()
        new_help.key = key
        new_help.entrytext = entrytext
        new_help.help_category = category
        if locks:
            new_help.locks.add(locks)
        if aliases:
            new_help.aliases.add(make_iter(aliases))
        if tags:
            new_help.tags.batch_add(*tags)
        new_help.save()
        return new_help
    except IntegrityError:
        string = "Could not add help entry: key '%s' already exists." % key
        logger.log_err(string)
        return None
    except Exception:
        logger.log_trace()
        return None

    signals.SIGNAL_HELPENTRY_POST_CREATE.send(sender=new_help)


# alias
help_entry = create_help_entry


#
# Comm system methods


def create_message(
    senderobj, message, receivers=None, locks=None, tags=None,
        header=None, **kwargs):
    """
    Create a new communication Msg. Msgs represent a unit of
    database-persistent communication between entites.

    Args:
        senderobj (Object, Account, Script, str or list): The entity (or
            entities) sending the Msg. If a `str`, this is the id-string
            for an external sender type.
        message (str): Text with the message. Eventual headers, titles
            etc should all be included in this text string. Formatting
            will be retained.
        receivers (Object, Account, Script, str or list): An Account/Object to send
            to, or a list of them. If a string, it's an identifier for an external
            receiver.
        locks (str): Lock definition string.
        tags (list): A list of tags or tuples `(tag, category)`.
        header (str): Mime-type or other optional information for the message

    Notes:
        The Comm system is created to be very open-ended, so it's fully
        possible to let a message both go several receivers at the same time,
        it's up to the command definitions to limit this as desired.

    """
    if 'channels' in kwargs:
        raise DeprecationWarning(
            "create_message() does not accept 'channel' kwarg anymore "
            "- channels no longer accept Msg objects."
        )

    global _Msg
    if not _Msg:
        from evennia.comms.models import Msg as _Msg
    if not message:
        # we don't allow empty messages.
        return None
    new_message = _Msg(db_message=message)
    new_message.save()
    for sender in make_iter(senderobj):
        new_message.senders = sender
    new_message.header = header
    for receiver in make_iter(receivers):
        new_message.receivers = receiver
    if locks:
        new_message.locks.add(locks)
    if tags:
        new_message.tags.batch_add(*tags)

    new_message.save()
    return new_message


message = create_message
create_msg = create_message


def create_channel(
    key, aliases=None, desc=None, locks=None, keep_log=True, typeclass=None, tags=None
):
    """
    Create A communication Channel. A Channel serves as a central hub
    for distributing Msgs to groups of people without specifying the
    receivers explicitly. Instead accounts may 'connect' to the channel
    and follow the flow of messages. By default the channel allows
    access to all old messages, but this can be turned off with the
    keep_log switch.

    Args:
        key (str): This must be unique.

    Keyword Args:
        aliases (list of str): List of alternative (likely shorter) keynames.
        desc (str): A description of the channel, for use in listings.
        locks (str): Lockstring.
        keep_log (bool): Log channel throughput.
        typeclass (str or class): The typeclass of the Channel (not
            often used).
        tags (list): A list of tags or tuples `(tag, category)`.

    Returns:
        channel (Channel): A newly created channel.

    """
    typeclass = typeclass if typeclass else settings.BASE_CHANNEL_TYPECLASS

    if isinstance(typeclass, str):
        # a path is given. Load the actual typeclass
        typeclass = class_from_module(typeclass, settings.TYPECLASS_PATHS)

    # create new instance
    new_channel = typeclass(db_key=key)

    # store call signature for the signal
    new_channel._createdict = dict(
        key=key, aliases=aliases, desc=desc, locks=locks, keep_log=keep_log, tags=tags
    )

    # this will trigger the save signal which in turn calls the
    # at_first_save hook on the typeclass, where the _createdict can be
    # used.
    new_channel.save()

    signals.SIGNAL_CHANNEL_POST_CREATE.send(sender=new_channel)

    return new_channel


channel = create_channel


#
# Account creation methods
#


def create_account(
    key,
    email,
    password,
    typeclass=None,
    is_superuser=False,
    locks=None,
    permissions=None,
    tags=None,
    attributes=None,
    report_to=None,
):
    """
    This creates a new account.

    Args:
        key (str): The account's name. This should be unique.
        email (str or None): Email on valid addr@addr.domain form. If
            the empty string, will be set to None.
        password (str): Password in cleartext.

    Keyword Args:
        typeclass (str): The typeclass to use for the account.
        is_superuser (bool): Wether or not this account is to be a superuser
        locks (str): Lockstring.
        permission (list): List of permission strings.
        tags (list): List of Tags on form `(key, category[, data])`
        attributes (list): List of Attributes on form
             `(key, value [, category, [,lockstring [, default_pass]]])`
        report_to (Object): An object with a msg() method to report
            errors to. If not given, errors will be logged.

    Returns:
        Account: The newly created Account.
    Raises:
        ValueError: If `key` already exists in database.


    Notes:
        Usually only the server admin should need to be superuser, all
        other access levels can be handled with more fine-grained
        permissions or groups. A superuser bypasses all lock checking
        operations and is thus not suitable for play-testing the game.

    """
    global _AccountDB
    if not _AccountDB:
        from evennia.accounts.models import AccountDB as _AccountDB

    typeclass = typeclass if typeclass else settings.BASE_ACCOUNT_TYPECLASS
    locks = make_iter(locks) if locks is not None else None
    permissions = make_iter(permissions) if permissions is not None else None
    tags = make_iter(tags) if tags is not None else None
    attributes = make_iter(attributes) if attributes is not None else None

    if isinstance(typeclass, str):
        # a path is given. Load the actual typeclass.
        typeclass = class_from_module(typeclass, settings.TYPECLASS_PATHS)

    # setup input for the create command. We use AccountDB as baseclass
    # here to give us maximum freedom (the typeclasses will load
    # correctly when each object is recovered).

    if not email:
        email = None
    if _AccountDB.objects.filter(username__iexact=key):
        raise ValueError("An Account with the name '%s' already exists." % key)

    # this handles a given dbref-relocate to an account.
    report_to = dbid_to_obj(report_to, _AccountDB)

    # create the correct account entity, using the setup from
    # base django auth.
    now = timezone.now()
    email = typeclass.objects.normalize_email(email)
    new_account = typeclass(
        username=key,
        email=email,
        is_staff=is_superuser,
        is_superuser=is_superuser,
        last_login=now,
        date_joined=now,
    )
    if password is not None:
        # the password may be None for 'fake' accounts, like bots
        valid, error = new_account.validate_password(password, new_account)
        if not valid:
            raise error

        new_account.set_password(password)

    new_account._createdict = dict(
        locks=locks, permissions=permissions, report_to=report_to, tags=tags, attributes=attributes
    )
    # saving will trigger the signal that calls the
    # at_first_save hook on the typeclass, where the _createdict
    # can be used.
    new_account.save()

    # note that we don't send a signal here, that is sent from the Account.create helper method
    # instead.

    return new_account


# alias
account = create_account
