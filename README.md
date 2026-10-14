# pibiDAV

Frappe/ERPNext v15 app (branch `v15`) that connects Frappe with CalDAV and CardDAV servers (Nextcloud included):

- **Contacts (CardDAV):** two-way sync of Contacts with the address books of each user, plus vCard tools that need no server (download a vCard or a vCard book, QR code, .vcf import).
- **Calendar (CalDAV):** two-way sync of Events with the calendars of each user, and e-mail invitations (iCalendar REQUEST).

## Installation

```bash
bench get-app pibidav --branch v15 <repository URL>
bench --site <site> install-app pibidav
```

It needs ERPNext (Custom Fields and buttons on Customer, Supplier, Project...). Python dependencies (icalendar, vobject, qrcode) are in `pyproject.toml`.

## Accounts and permissions

- **DAV Account** (one per user and service): server URL, DAV path, server login, timeout and an app password (Password field). Only an administrator creates accounts and sets the server and login. The owner connects the account with the Nextcloud Login Flow, or by typing an app password, and may only change that password and the enabled switch. The login used on the server must be the one set by the administrator, so an account is personal and cannot be shared.
- **DAV Collection:** the address books and calendars the account sees, read with *Discover*. The owner only switches Sync on or off.
- **DAV Card Link / DAV Cal Link / DAV Pending Contact:** sync bookkeeping. The owner can read them; only pibiDAV changes them.
- **DAV Audit Log:** every server operation (connect, pull, push, delete), without vCard or event content.
- TLS is always verified. Redirects are not followed. Servers in private networks are refused unless DAV Settings allows them.

## Sync

**DAV Settings** has a switch for each direction (pull and push, contacts and calendar) and the interval.

- **Pulling.** Every few minutes one job per account reads all its synced collections with sync-collection (RFC 6578).
- **New vCards.** A vCard that matches a Contact the user may edit is linked to it. A vCard that matches nothing waits in DAV Pending Contact, where the user creates or links the Contact.
- **Events.** Events are created as Private events of the account owner. Changes in Frappe are pushed to every calendar the Event is linked to.
- **Conflicts.** If an item changed on the server and in Frappe since the last sync, it is not overwritten, and a *Conflict* row is written to DAV Audit Log.
- **Contact UID.** `Contact.dav_uid` keeps the vCard UID of each contact. The UIDs of the old pibicard app were adopted by a patch.

## Nextcloud files

They are in **pibidrive** (libraries, cloud button, folders per record and public links). pibidav kept them until 14/10/2026; a patch removed that part and its data was migrated to pibidrive.

## Development

Code changes go to branch `v15`. Doctypes are changed by editing their JSON and running `bench --site <site> migrate`. Patches are in `pibidav/patches/`.

## License

MIT
