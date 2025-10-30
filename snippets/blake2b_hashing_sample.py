import hashlib
import json

traits = ["Craftsman", "Pragmatic", "Curious", "Methodical", "Driven", "Collaborator"]

key = "Close-92418e70"
key_bytes = key.encode("utf-8")


def hash_trait(trait):
    trait_bytes = trait.encode("utf-8")
    return hashlib.blake2b(trait_bytes, digest_size=64, key=key_bytes).hexdigest()


print(json.dumps([hash_trait(t) for t in traits]))
