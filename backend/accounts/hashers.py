from django.contrib.auth.hashers import Argon2PasswordHasher


class FastArgon2PasswordHasher(Argon2PasswordHasher):
    """Argon2id with the settings OWASP recommends (19 MiB of memory, 2 passes, 1 thread).

    Django's default password hasher (PBKDF2, 1.5 million rounds) takes about 1 second of CPU
    per login, which is around 10 seconds on Render's free plan (a tenth of a CPU). This takes
    about 0.03 seconds and is still strong, because guessing needs the memory as well as the time.
    """

    time_cost = 2
    memory_cost = 19 * 1024  # KiB
    parallelism = 1
