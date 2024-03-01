"""Model factories."""
import factory
from django.contrib.auth import get_user_model


class UserF(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(
        lambda n: u'username %s' % n
    )
