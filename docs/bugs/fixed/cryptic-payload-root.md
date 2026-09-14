# Bug: Cryptic payload outline root

Request #65 displays $ {8} as the root outline label, which looks like an
unresolved template expression. It means the payload has eight top-level fields.
Use a plain-language label instead. Tracked by task 049.

Fixed by task 049: Request payload · 8 fields, with dynamic count and correct
singular/plural units. Build and worker/outline browser fixtures pass.
