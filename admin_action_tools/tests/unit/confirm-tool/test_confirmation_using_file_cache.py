"""
Ensure that files are saved during confirmation
Without file changes, Django is relied on

With file changes, we cache the object, save it with
the files if new, or add files to existing obj and save

Then send the rest of the changes to Django to handle

This is arguably the most we fiddle with the Django request
Thus we should test it extensively
"""
import time
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from admin_action_tools.constants import CACHE_KEYS, CONFIRMATION_RECEIVED
from admin_action_tools.file_cache import FileCache
from admin_action_tools.tests.helpers import AdminConfirmTestCase
from admin_action_tools.utils import format_cache_key
from tests.factories import ItemFactory, ShopFactory
from tests.market.admin import ItemAdmin
from tests.market.models import Item, Shop


class TestConfirmationUsingFileCache(AdminConfirmTestCase):
    def setUp(self):
        # Load the Change Item Page
        ItemAdmin.confirm_change = True
        ItemAdmin.fields = ["name", "price", "file", "image", "currency"]
        ItemAdmin.save_as = True
        ItemAdmin.save_as_continue = True

        self.image_path = "admin_action_tools/tests/snapshot/screenshot.png"
        f = SimpleUploadedFile(
            name="test_file.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )
        i = SimpleUploadedFile(
            name="test_image.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )
        self.item = ItemFactory(name="Not name", file=f, image=i)

        return super().setUp()

    def test_save_as_continue_true_should_not_redirect_to_changelist(self):
        item = self.item
        # Load the Change Item Page
        ItemAdmin.save_as_continue = True

        # Upload new image and remove file
        i2 = SimpleUploadedFile(
            name="test_image2.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )
        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "file": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_saveasnew": True,
        }

        # Set cache
        cache_item = Item(
            name=data["name"],
            price=data["price"],
            currency=data["currency"],
            image=i2,
        )
        file_cache = FileCache()
        file_cache.set(format_cache_key(model="Item", field="image"), i2)

        cache.set(CACHE_KEYS["object"], cache_item)
        cache.set(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertIn("You may edit it again below.", message)

        # Should not have redirected to changelist
        self.assertEqual(response.url, f"/admin/market/item/{self.item.id + 1}/change/")

        # Should not have changed existing item
        item.refresh_from_db()
        self.assertEqual(item.name, "Not name")
        self.assertEqual(item.file.name.count("test_file"), 1)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertFalse(new_item.file)
        self.assertEqual(new_item.image.name.count("test_image2"), 1)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_save_as_continue_false_should_redirect_to_changelist(self):
        item = self.item
        # Load the Change Item Page
        ItemAdmin.save_as_continue = False

        # Upload new image and remove file
        i2 = SimpleUploadedFile(
            name="test_image2.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )
        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "file": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_saveasnew": True,
        }

        # Set cache
        cache_item = Item(
            name=data["name"],
            price=data["price"],
            currency=data["currency"],
            image=i2,
        )
        file_cache = FileCache()
        file_cache.set(format_cache_key(model="Item", field="image"), i2)

        cache.set(CACHE_KEYS["object"], cache_item)
        cache.set(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        item.refresh_from_db()
        self.assertEqual(item.name, "Not name")
        self.assertEqual(item.file.name.count("test_file"), 1)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertFalse(new_item.file)
        self.assertEqual(new_item.image.name.count("test_image2"), 1)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_saveasnew_without_any_file_changes_should_save_new_instance_without_files(
        self,
    ):
        item = self.item

        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "file": "",
            "image": "",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_saveasnew": True,
        }

        # Set cache
        cache_item = Item(
            name=data["name"],
            price=data["price"],
            currency=data["currency"],
        )

        cache.set(CACHE_KEYS["object"], cache_item)
        cache.set(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertIn("You may edit it again below.", message)

        # Should not have redirected to changelist
        self.assertEqual(response.url, f"/admin/market/item/{self.item.id + 1}/change/")

        # Should not have changed existing item
        item.refresh_from_db()
        self.assertEqual(item.name, "Not name")
        self.assertEqual(item.file.name.count("test_file"), 1)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        # In Django (by default), the save as new does not transfer over the files
        self.assertFalse(new_item.file)
        self.assertFalse(new_item.image)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_add_with_upload_file_should_save_new_instance_with_files(self):
        # Upload new file
        f2 = SimpleUploadedFile(
            name="test_file2.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )

        # Request.POST
        data = {
            "name": "name",
            "price": 2.0,
            "image": "",
            "file": f2,
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_add": True,
            "_save": True,
        }

        # Set cache
        cache_item = Item(name=data["name"], price=data["price"], currency=data["currency"], file=f2)

        cache.set(CACHE_KEYS["object"], cache_item)
        cache.set(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_add"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post("/admin/market/item/add/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should not have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Not name")
        self.assertEqual(self.item.file.name.count("test_file"), 1)
        self.assertEqual(self.item.image.name.count("test_image2"), 0)
        self.assertEqual(self.item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=self.item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertIsNotNone(new_item.file)
        self.assertFalse(new_item.image)

        self.assertRegex(new_item.file.name, r"test_file2.*\.jpg$")

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_add_without_cached_post_should_save_new_instance_with_file(self):
        # Upload new file
        f2 = SimpleUploadedFile(
            name="test_file2.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )

        # Request.POST
        data = {
            "name": "name",
            "price": 2.0,
            "image": "",
            "file": f2,
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_add": True,
            "_save": True,
        }

        # Set cache
        cache_item = Item(name=data["name"], price=data["price"], currency=data["currency"], file=f2)

        cache.set(CACHE_KEYS["object"], cache_item)
        # Make sure there's no post cached post
        cache.delete(CACHE_KEYS["post"])

        # Click "Yes, I'm Sure"
        del data["_confirm_add"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post("/admin/market/item/add/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should not have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Not name")
        self.assertEqual(self.item.file.name.count("test_file"), 1)
        self.assertEqual(self.item.image.name.count("test_image2"), 0)
        self.assertEqual(self.item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=self.item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertFalse(new_item.image)

        # Able to save the cached file since cached object was there even though cached post was not
        self.assertRegex(new_item.file.name, r"test_file2.*\.jpg$")

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_add_without_cached_object_should_save_new_instance_but_not_have_file(self):
        # Request.POST
        data = {
            "name": "name",
            "price": 2.0,
            "image": "",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_add": True,
            "_save": True,
        }

        # Make sure there's no post cached obj
        cache.delete(CACHE_KEYS["object"])
        cache.set(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_add"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post("/admin/market/item/add/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should not have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Not name")
        self.assertEqual(self.item.file.name.count("test_file"), 1)
        self.assertEqual(self.item.image.name.count("test_image2"), 0)
        self.assertEqual(self.item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=self.item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertFalse(new_item.image)

        # FAILED to save the file, because cached item was not there
        self.assertFalse(new_item.file)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_add_without_any_cache_should_save_new_instance_but_not_have_file(self):
        # Request.POST
        data = {
            "name": "name",
            "price": 2.0,
            "image": "",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_add": True,
            "_save": True,
        }

        # Make sure there's no cache
        cache.delete(CACHE_KEYS["object"])
        cache.delete(CACHE_KEYS["post"])

        # Click "Yes, I'm Sure"
        del data["_confirm_add"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post("/admin/market/item/add/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should not have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Not name")
        self.assertEqual(self.item.file.name.count("test_file"), 1)
        self.assertEqual(self.item.image.name.count("test_image2"), 0)
        self.assertEqual(self.item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=self.item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertFalse(new_item.image)

        # FAILED to save the file, because cached item was not there
        self.assertFalse(new_item.file)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_change_without_cached_post_should_save_file_changes(self):
        item = self.item
        # Load the Change Item Page
        ItemAdmin.save_as_continue = False

        # Upload new image and remove file
        i2 = SimpleUploadedFile(
            name="test_image2.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )
        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "image": i2,
            "file": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_saveasnew": True,
        }

        # Set cache
        cache_item = Item(
            name=data["name"],
            price=data["price"],
            currency=data["currency"],
            image=i2,
        )
        file_cache = FileCache()
        file_cache.set(format_cache_key(model="Item", field="image"), i2)

        cache.set(CACHE_KEYS["object"], cache_item)
        # Ensure no cached post
        cache.delete(CACHE_KEYS["post"])

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        # Image would have been in FILES and not in POST
        del data["image"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        item.refresh_from_db()
        self.assertEqual(item.name, "Not name")
        self.assertEqual(item.file.name.count("test_file"), 1)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        # Should have cleared `file` since clear was selected
        self.assertFalse(new_item.file)
        self.assertIsNotNone(new_item.image)
        # Saved cached file from cached obj even if cached post was missing
        self.assertIn("test_image2", new_item.image.name)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_change_without_cached_object_should_save_but_without_file_changes(self):
        item = self.item
        # Load the Change Item Page
        ItemAdmin.save_as_continue = False

        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "file": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_saveasnew": True,
        }

        # Ensure no cached obj
        cache.delete(CACHE_KEYS["object"])
        cache.set(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        item.refresh_from_db()
        self.assertEqual(item.name, "Not name")
        self.assertEqual(item.file.name.count("test_file"), 1)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertFalse(new_item.file)
        # FAILED to save image
        self.assertFalse(new_item.image)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_change_without_any_cache_should_save_but_not_have_file_changes(self):
        item = self.item
        # Load the Change Item Page
        ItemAdmin.save_as_continue = False

        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "file": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_saveasnew": True,
        }

        # Ensure no cache
        cache.delete(CACHE_KEYS["object"])
        cache.delete(CACHE_KEYS["post"])

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/2/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should not have changed existing item
        item.refresh_from_db()
        self.assertEqual(item.name, "Not name")
        self.assertEqual(item.file.name.count("test_file"), 1)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have saved new item
        self.assertEqual(Item.objects.count(), 2)
        new_item = Item.objects.filter(id=item.id + 1).first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.name, data["name"])
        self.assertEqual(new_item.price, data["price"])
        self.assertEqual(new_item.currency, data["currency"])
        self.assertFalse(new_item.file)
        # FAILED to save image
        self.assertFalse(new_item.image)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_change_without_changing_file_should_save_changes(self):
        item = self.item
        # Load the Change Item Page
        ItemAdmin.save_as_continue = False

        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "file": "",
            "image": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_save": True,
        }

        # Set cache
        cache_item = Item(
            name=data["name"],
            price=data["price"],
            currency=data["currency"],
        )

        cache.get(CACHE_KEYS["object"], cache_item)
        cache.get(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/1/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should have changed existing item
        self.assertEqual(Item.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.name, "name")
        # Should have cleared if requested
        self.assertFalse(item.file.name)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    @mock.patch("admin_action_tools.admin.confirm_tool.CACHE_TIMEOUT", 1)
    def test_old_cache_should_not_be_used(self):
        item = self.item

        # Upload new image and remove file
        i2 = SimpleUploadedFile(
            name="test_image2.jpg",
            content=open(self.image_path, "rb").read(),
            content_type="image/jpeg",
        )
        # Click "Save And Continue"
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "image": i2,
            "file": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_continue": True,
        }
        response = self.client.post(f"/admin/market/item/{item.id}/change/", data=data)

        # Should be shown confirmation page
        self._assertSubmitHtml(
            rendered_content=response.rendered_content,
            save_action="_continue",
            multipart_form=True,
        )

        # Should have cached the unsaved item
        cached_item = cache.get(CACHE_KEYS["object"])
        self.assertIsNotNone(cached_item)

        # Should not have saved the changes yet
        self.assertEqual(Item.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.name, "Not name")
        self.assertIsNotNone(item.file)
        self.assertIsNotNone(item.image)

        # Wait for cache to time out

        time.sleep(1)

        # Check that it did time out
        cached_item = cache.get(CACHE_KEYS["object"])
        self.assertIsNone(cached_item)

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data["image"] = ""
        data[CONFIRMATION_RECEIVED] = True
        response = self.client.post(f"/admin/market/item/{item.id}/change/", data=data)

        # Should not have redirected to changelist
        self.assertEqual(response.url, f"/admin/market/item/{item.id}/change/")

        # Should have saved item
        self.assertEqual(Item.objects.count(), 1)
        saved_item = Item.objects.all().first()
        self.assertEqual(saved_item.name, data["name"])
        self.assertEqual(saved_item.price, data["price"])
        self.assertEqual(saved_item.currency, data["currency"])
        self.assertFalse(saved_item.file)

        # SHOULD not have saved image since it was in the old cache
        self.assertNotIn("test_image2", saved_item.image)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_cache_with_incorrect_model_should_not_be_used(self):
        item = self.item
        # Load the Change Item Page
        ItemAdmin.save_as_continue = False

        # Request.POST
        data = {
            "id": item.id,
            "name": "name",
            "price": 2.0,
            "file": "",
            "file-clear": "on",
            "currency": Item.VALID_CURRENCIES[0][0],
            "_confirm_change": True,
            "_save": True,
        }

        # Set cache to incorrect model
        cache_obj = Shop(name="ShopName")

        cache.set(CACHE_KEYS["object"], cache_obj)
        cache.set(CACHE_KEYS["post"], data)

        # Click "Yes, I'm Sure"
        del data["_confirm_change"]
        data[CONFIRMATION_RECEIVED] = True

        with mock.patch.object(ItemAdmin, "message_user") as message_user:
            response = self.client.post(f"/admin/market/item/{self.item.id}/change/", data=data)
            # Should show message to user with correct obj and path
            message_user.assert_called_once()
            message = message_user.call_args[0][1]
            self.assertIn("/admin/market/item/1/change/", message)
            self.assertIn(data["name"], message)
            self.assertNotIn("You may edit it again below.", message)

        # Should have redirected to changelist
        self.assertEqual(response.url, "/admin/market/item/")

        # Should have changed existing item
        self.assertEqual(Item.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.name, "name")
        # Should have cleared if requested
        self.assertFalse(item.file.name)
        self.assertEqual(item.image.name.count("test_image2"), 0)
        self.assertEqual(item.image.name.count("test_image"), 1)

        # Should have cleared cache
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))

    def test_form_without_files_should_not_use_cache(self):
        cache.delete_many(CACHE_KEYS.values())
        shop = ShopFactory()
        # Click "Save And Continue"
        data = {
            "id": shop.id,
            "name": "name",
            "_confirm_change": True,
            "_continue": True,
        }
        response = self.client.post(f"/admin/market/shop/{shop.id}/change/", data=data)

        # Should be shown confirmation page
        self._assertSubmitHtml(rendered_content=response.rendered_content, save_action="_continue")

        # Should not have set cache since not multipart form
        for key in CACHE_KEYS.values():
            self.assertIsNone(cache.get(key))
