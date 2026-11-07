/**
 * Kitchen Menu Management Page
 * Allows kitchen owners to manage dishes, pricing, availability, and ingredient recipe links.
 */

import { useState, useEffect } from 'react';
import kitchenApi, {
  MenuItemWithRecipe,
  Ingredient,
  MenuItemCreateInput,
} from '../../services/kitchenApi';
import {
  UtensilsCrossed,
  Plus,
  Edit2,
  Trash2,
  Check,
  X,
  Layers,
  RefreshCw,
  Search,
  DollarSign,
  AlertCircle,
  Upload,
} from 'lucide-react';

export default function KitchenMenu() {
  const [menuItems, setMenuItems] = useState<MenuItemWithRecipe[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // Manual Image Upload Modal States
  const [uploadModalItem, setUploadModalItem] = useState<MenuItemWithRecipe | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [uploadImageUrl, setUploadImageUrl] = useState('');
  const [urlPreviewValid, setUrlPreviewValid] = useState<boolean | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Item Create/Edit Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MenuItemWithRecipe | null>(null);
  const [formData, setFormData] = useState<MenuItemCreateInput>({
    name: '',
    category: 'Rice Bowl',
    cuisine: 'Indian',
    price: 150,
    is_available: true,
    is_veg: true,
    description: '',
  });

  // Recipe Linking & Management Modal
  const [recipeModalItem, setRecipeModalItem] = useState<MenuItemWithRecipe | null>(null);
  const [selectedIngredientId, setSelectedIngredientId] = useState('');
  const [recipeQuantity, setRecipeQuantity] = useState(0.2);
  const [recipeValidationError, setRecipeValidationError] = useState<string | null>(null);
  const [editingIngredientId, setEditingIngredientId] = useState<string | null>(null);
  const [editingQuantity, setEditingQuantity] = useState<number>(0);
  const [confirmDeleteIngredient, setConfirmDeleteIngredient] = useState<{ id: string; name: string } | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [itemsData, ingredientsData] = await Promise.all([
        kitchenApi.getMenuItems(),
        kitchenApi.getIngredients(),
      ]);
      setMenuItems(itemsData);
      setIngredients(ingredientsData);
    } catch (err: any) {
      setError(err?.detail || 'Failed to load menu items.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleOpenCreate = () => {
    setEditingItem(null);
    setFormData({
      name: '',
      category: 'Rice Bowl',
      cuisine: 'Indian',
      price: 150,
      is_available: true,
      is_veg: true,
      description: '',
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (item: MenuItemWithRecipe) => {
    setEditingItem(item);
    setFormData({
      name: item.name,
      category: item.category,
      cuisine: item.cuisine,
      price: item.price,
      is_available: item.is_available,
      is_veg: item.is_veg,
      description: item.description || '',
    });
    setIsModalOpen(true);
  };

  const handleSaveItem = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingItem) {
        const updated = await kitchenApi.updateMenuItem(editingItem.id, formData);
        setMenuItems(menuItems.map((m) => (m.id === updated.id ? updated : m)));
      } else {
        const created = await kitchenApi.createMenuItem(formData);
        setMenuItems([...menuItems, created]);
      }
      setIsModalOpen(false);
    } catch (err: any) {
      alert(err?.detail || 'Failed to save menu item.');
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    if (!window.confirm('Are you sure you want to delete this menu item?')) return;
    try {
      await kitchenApi.deleteMenuItem(itemId);
      setMenuItems(menuItems.filter((m) => m.id !== itemId));
    } catch (err: any) {
      alert(err?.detail || 'Failed to delete menu item.');
    }
  };

  const handleToggleAvailability = async (item: MenuItemWithRecipe) => {
    try {
      const updated = await kitchenApi.updateMenuItem(item.id, {
        is_available: !item.is_available,
      });
      setMenuItems(menuItems.map((m) => (m.id === updated.id ? updated : m)));
    } catch (err: any) {
      alert(err?.detail || 'Failed to toggle availability.');
    }
  };

  // Recipe Linking & Editing Handlers
  const handleLinkIngredient = async (e: React.FormEvent) => {
    e.preventDefault();
    setRecipeValidationError(null);
    if (!recipeModalItem) return;

    if (!selectedIngredientId) {
      setRecipeValidationError('Please select an ingredient from your kitchen inventory.');
      return;
    }

    const qty = Number(recipeQuantity);
    if (isNaN(qty) || qty <= 0) {
      setRecipeValidationError('Quantity required must be strictly greater than 0.');
      return;
    }

    // Check duplicate
    const exists = recipeModalItem.recipe_ingredients.find(
      (r) => r.ingredient_id === selectedIngredientId
    );
    if (exists) {
      setRecipeValidationError(
        `'${exists.ingredient_name}' is already in this recipe. Use the Edit button below to change its quantity.`
      );
      return;
    }

    try {
      await kitchenApi.linkRecipeIngredient(recipeModalItem.id, {
        ingredient_id: selectedIngredientId,
        quantity_required: qty,
      });
      // Refresh items to get updated recipe list
      const updatedItems = await kitchenApi.getMenuItems();
      setMenuItems(updatedItems);
      const current = updatedItems.find((i) => i.id === recipeModalItem.id);
      if (current) setRecipeModalItem(current);
      setSelectedIngredientId('');
      setRecipeQuantity(0.2);
      setRecipeValidationError(null);
    } catch (err: any) {
      setRecipeValidationError(err?.detail || 'Failed to link ingredient to recipe.');
    }
  };

  const handleSaveEditRecipeIngredient = async (ingredientId: string) => {
    if (!recipeModalItem) return;
    const qty = Number(editingQuantity);
    if (isNaN(qty) || qty <= 0) {
      alert('Quantity must be strictly greater than 0.');
      return;
    }
    try {
      await kitchenApi.linkRecipeIngredient(recipeModalItem.id, {
        ingredient_id: ingredientId,
        quantity_required: qty,
      });
      const updatedItems = await kitchenApi.getMenuItems();
      setMenuItems(updatedItems);
      const current = updatedItems.find((i) => i.id === recipeModalItem.id);
      if (current) setRecipeModalItem(current);
      setEditingIngredientId(null);
    } catch (err: any) {
      alert(err?.detail || 'Failed to update recipe ingredient quantity.');
    }
  };

  const handleConfirmRemoveIngredient = async () => {
    if (!recipeModalItem || !confirmDeleteIngredient) return;
    try {
      await kitchenApi.unlinkRecipeIngredient(recipeModalItem.id, confirmDeleteIngredient.id);
      const updatedItems = await kitchenApi.getMenuItems();
      setMenuItems(updatedItems);
      const current = updatedItems.find((i) => i.id === recipeModalItem.id);
      if (current) setRecipeModalItem(current);
      setConfirmDeleteIngredient(null);
    } catch (err: any) {
      alert(err?.detail || 'Failed to remove ingredient from recipe.');
    }
  };

  const closeUploadModal = () => {
    setUploadModalItem(null);
    setSelectedFile(null);
    if (filePreview) {
      URL.revokeObjectURL(filePreview);
    }
    setFilePreview(null);
    setUploadImageUrl('');
    setUrlPreviewValid(null);
    setModalError(null);
    setUploadingImage(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setModalError(null);
    const file = e.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      if (filePreview) URL.revokeObjectURL(filePreview);
      setFilePreview(null);
      return;
    }
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    const validExts = ['.png', '.jpg', '.jpeg', '.webp'];
    if (!validExts.includes(ext)) {
      setModalError('Invalid file type. Allowed formats are PNG, JPG, JPEG, and WEBP.');
      setSelectedFile(null);
      if (filePreview) URL.revokeObjectURL(filePreview);
      setFilePreview(null);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setModalError('File size exceeds the 5 MB limit.');
      setSelectedFile(null);
      if (filePreview) URL.revokeObjectURL(filePreview);
      setFilePreview(null);
      return;
    }
    setSelectedFile(file);
    if (filePreview) URL.revokeObjectURL(filePreview);
    setFilePreview(URL.createObjectURL(file));
  };

  const handleUploadSelectedFile = async () => {
    if (!uploadModalItem || !selectedFile) return;
    try {
      setUploadingImage(true);
      setModalError(null);
      const updated = await kitchenApi.uploadMenuItemImageFile(uploadModalItem.id, selectedFile);
      setMenuItems((prev) => prev.map((m) => (m.id === uploadModalItem.id ? updated : m)));
      closeUploadModal();
    } catch (err: any) {
      setModalError(err?.detail || err?.message || 'Failed to upload image file.');
    } finally {
      setUploadingImage(false);
    }
  };

  const handleSaveImageUrl = async () => {
    if (!uploadModalItem || !uploadImageUrl.trim()) return;
    try {
      setUploadingImage(true);
      setModalError(null);
      const updated = await kitchenApi.uploadMenuItemImageUrl(uploadModalItem.id, uploadImageUrl.trim());
      setMenuItems((prev) => prev.map((m) => (m.id === uploadModalItem.id ? updated : m)));
      closeUploadModal();
    } catch (err: any) {
      setModalError(err?.detail || err?.message || 'Failed to save image URL.');
    } finally {
      setUploadingImage(false);
    }
  };

  const handleRemoveImage = async (item: MenuItemWithRecipe) => {
    try {
      const updated = await kitchenApi.removeMenuItemImage(item.id);
      setMenuItems((prev) => prev.map((m) => (m.id === item.id ? updated : m)));
    } catch (err: any) {
      alert(err?.detail || 'Failed to remove image.');
    }
  };

  const filteredItems = menuItems.filter((item) =>
    item.name.toLowerCase().includes(search.toLowerCase()) ||
    item.category.toLowerCase().includes(search.toLowerCase()) ||
    item.cuisine.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
        <div>
          <h1 className="text-2xl font-black text-[#172033] tracking-tight">Menu & Recipes</h1>
          <p className="text-sm text-gray-500">Configure dishes, availability, and ingredient consumption formulas.</p>
        </div>

        <button
          onClick={handleOpenCreate}
          className="flex items-center space-x-2 px-5 py-2.5 bg-[#166534] hover:bg-emerald-800 text-white rounded-xl text-sm font-bold transition-colors shadow-xs"
        >
          <Plus className="w-4 h-4" />
          <span>Add Menu Item</span>
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="w-5 h-5 text-gray-400 absolute left-4 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search dishes by name, category, or cuisine..."
          className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200/80 rounded-2xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
        />
      </div>

      {/* Menu Cards */}
      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
        </div>
      ) : error ? (
        <div className="p-6 bg-red-50 text-red-700 rounded-2xl border border-red-200 text-center">
          <p>{error}</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200/80 p-12 text-center">
          <UtensilsCrossed className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-700">No menu items found</h3>
          <p className="text-sm text-gray-400 mt-1">Add your first dish using the button above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className={`bg-white rounded-2xl border transition-all p-5 shadow-xs flex flex-col justify-between ${
                item.is_available ? 'border-gray-200/80' : 'border-gray-200 opacity-60 bg-gray-50/50'
              }`}
            >
              <div>
                {/* Dish Image Preview */}
                {(() => {
                  const displayImage = item.manual_image_url || item.image_url;

                  return (
                    <div className="relative w-full h-44 mb-3 rounded-xl overflow-hidden bg-gray-100 flex items-center justify-center border border-gray-200/80 group">
                      {displayImage ? (
                        <img
                          src={displayImage}
                          alt={item.name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="flex flex-col items-center justify-center text-gray-400 p-4 text-center">
                          <UtensilsCrossed className="w-9 h-9 mb-1.5 text-gray-300" />
                          <span className="text-[11px] font-medium text-gray-400">No photo uploaded</span>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Image Management Action Bar */}
                <div className="flex flex-wrap items-center gap-1.5 mb-3">
                  {!item.manual_image_url && !item.image_url ? (
                    <button
                      type="button"
                      onClick={() => {
                        setUploadModalItem(item);
                        setSelectedFile(null);
                        setFilePreview(null);
                        setUploadImageUrl('');
                        setUrlPreviewValid(null);
                        setModalError(null);
                      }}
                      className="w-full inline-flex items-center justify-center gap-1 px-2.5 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-xs font-semibold transition-colors"
                    >
                      <Upload className="w-3.5 h-3.5" /> Upload Image
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          setUploadModalItem(item);
                          setSelectedFile(null);
                          setFilePreview(null);
                          setUploadImageUrl('');
                          setUrlPreviewValid(null);
                          setModalError(null);
                        }}
                        className="flex-1 inline-flex items-center justify-center gap-1 px-2.5 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-xs font-semibold transition-colors"
                      >
                        <Upload className="w-3.5 h-3.5" /> Replace Image
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveImage(item)}
                        className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
                        title="Remove Image"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                </div>

                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center ${
                        item.is_veg ? 'border-green-600' : 'border-red-600'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${item.is_veg ? 'bg-green-600' : 'bg-red-600'}`} />
                    </span>
                    <h3 className="font-bold text-base text-[#172033]">{item.name}</h3>
                  </div>
                  <span className="text-base font-black text-[#166534]">₹{item.price.toFixed(2)}</span>
                </div>

                <p className="text-xs text-gray-500 line-clamp-2 mb-3">
                  {item.description || 'No description provided.'}
                </p>

                <div className="flex flex-wrap gap-1.5 mb-4">
                  <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs font-medium rounded-lg">
                    {item.category}
                  </span>
                  <span className="px-2 py-0.5 bg-emerald-50 text-[#166534] text-xs font-medium rounded-lg">
                    {item.cuisine}
                  </span>
                </div>

                {/* Recipe Ingredients Summary */}
                <div className="p-3 bg-gray-50 rounded-xl mb-4 text-xs border border-gray-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-500 font-bold uppercase tracking-wider text-[10px]">
                      Recipe Formula
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                        item.recipe_ingredients.length > 0
                          ? 'bg-emerald-100 text-[#166534]'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {item.recipe_ingredients.length} {item.recipe_ingredients.length === 1 ? 'ITEM' : 'ITEMS'}
                    </span>
                  </div>
                  {item.recipe_ingredients.length === 0 ? (
                    <div className="py-2 text-center">
                      <p className="text-gray-400 italic text-xs mb-1">No ingredients linked yet.</p>
                      <button
                        type="button"
                        onClick={() => {
                          setRecipeModalItem(item);
                          setRecipeValidationError(null);
                        }}
                        className="text-xs text-[#166534] font-bold hover:underline"
                      >
                        + Configure recipe ingredients
                      </button>
                    </div>
                  ) : (
                    <ul className="space-y-1.5 max-h-32 overflow-y-auto divide-y divide-gray-100">
                      {item.recipe_ingredients.map((r) => (
                        <li key={r.ingredient_id} className="pt-1 first:pt-0 flex justify-between items-center text-gray-700">
                          <span className="font-medium truncate mr-2">{r.ingredient_name}</span>
                          <span className="font-bold text-[#166534] whitespace-nowrap">
                            {r.quantity_required} {r.unit}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-gray-100 flex items-center justify-between gap-2">
                <button
                  onClick={() => {
                    setRecipeModalItem(item);
                    setRecipeValidationError(null);
                    setEditingIngredientId(null);
                    setConfirmDeleteIngredient(null);
                  }}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-orange-50 text-[#F97316] rounded-xl text-xs font-bold hover:bg-orange-100 transition-colors"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Recipe ({item.recipe_ingredients.length})</span>
                </button>

                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => handleToggleAvailability(item)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-colors ${
                      item.is_available
                        ? 'bg-emerald-50 text-[#166534] hover:bg-emerald-100'
                        : 'bg-red-50 text-red-600 hover:bg-red-100'
                    }`}
                  >
                    {item.is_available ? 'Available' : 'Unavailable'}
                  </button>

                  <button
                    onClick={() => handleOpenEdit(item)}
                    className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => handleDeleteItem(item.id)}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <form
            onSubmit={handleSaveItem}
            className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-[#172033]">
                {editingItem ? 'Edit Menu Item' : 'New Menu Item'}
              </h3>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Item Name</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g. Hyderabad Chicken Biryani"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Category</label>
                <input
                  type="text"
                  required
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  placeholder="e.g. Rice Bowl, Starters"
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Cuisine</label>
                <input
                  type="text"
                  required
                  value={formData.cuisine}
                  onChange={(e) => setFormData({ ...formData, cuisine: e.target.value })}
                  placeholder="e.g. Indian, Continental"
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Price (₹)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-500 mb-1">Description</label>
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of flavours and ingredients..."
                rows={2}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
              />
            </div>

            <div className="flex items-center space-x-6 pt-2">
              <label className="flex items-center space-x-2 cursor-pointer text-sm font-semibold text-gray-700">
                <input
                  type="checkbox"
                  checked={formData.is_veg}
                  onChange={(e) => setFormData({ ...formData, is_veg: e.target.checked })}
                  className="rounded-md text-[#166534] focus:ring-[#166534]"
                />
                <span>Vegetarian</span>
              </label>

              <label className="flex items-center space-x-2 cursor-pointer text-sm font-semibold text-gray-700">
                <input
                  type="checkbox"
                  checked={formData.is_available}
                  onChange={(e) => setFormData({ ...formData, is_available: e.target.checked })}
                  className="rounded-md text-[#166534] focus:ring-[#166534]"
                />
                <span>Available for Ordering</span>
              </label>
            </div>

            <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-sm font-semibold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-[#166534] text-white rounded-xl text-sm font-bold hover:bg-emerald-800 transition-colors"
              >
                Save Menu Item
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Real Recipe Management Modal (Section 1) */}
      {recipeModalItem && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-xl space-y-5 max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h3 className="text-lg font-bold text-[#172033]">
                  Recipe Formula: {recipeModalItem.name}
                </h3>
                <p className="text-xs text-gray-500">
                  Real ingredient requirements deducted from kitchen stock when orders are accepted.
                </p>
              </div>
              <button
                onClick={() => {
                  setRecipeModalItem(null);
                  setRecipeValidationError(null);
                  setEditingIngredientId(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Validation Message */}
            {recipeValidationError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{recipeValidationError}</span>
              </div>
            )}

            {/* Current Recipe Ingredients List */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase text-gray-500">
                  Linked Ingredients ({recipeModalItem.recipe_ingredients.length})
                </h4>
                <span className="text-[11px] text-gray-400">Deduction per serving</span>
              </div>

              {recipeModalItem.recipe_ingredients.length === 0 ? (
                <div className="p-6 border border-dashed border-gray-300 rounded-2xl text-center bg-gray-50/50">
                  <p className="text-sm font-semibold text-gray-600">No ingredients linked yet.</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Add ingredients from your kitchen inventory below to automate stock deduction.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden bg-white">
                  {recipeModalItem.recipe_ingredients.map((r) => {
                    const isEditing = editingIngredientId === r.ingredient_id;
                    return (
                      <div
                        key={r.ingredient_id}
                        className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-gray-50/60 transition-colors"
                      >
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-sm text-gray-900">{r.ingredient_name}</span>
                            <span className="text-[10px] font-semibold bg-gray-100 text-gray-600 px-2 py-0.5 rounded-md">
                              {r.unit}
                            </span>
                          </div>
                          {!isEditing ? (
                            <p className="text-xs text-[#166534] font-semibold mt-0.5">
                              {r.quantity_required} {r.unit} per order
                            </p>
                          ) : (
                            <div className="flex items-center space-x-2 mt-2">
                              <input
                                type="number"
                                step="any"
                                min="0.001"
                                value={editingQuantity}
                                onChange={(e) => setEditingQuantity(parseFloat(e.target.value) || 0)}
                                className="w-24 px-2 py-1 text-xs border border-gray-300 rounded-lg focus:ring-[#166534]"
                              />
                              <span className="text-xs text-gray-500 font-medium">{r.unit}</span>
                              <button
                                type="button"
                                onClick={() => handleSaveEditRecipeIngredient(r.ingredient_id)}
                                className="px-2.5 py-1 bg-[#166534] text-white rounded-lg text-xs font-bold hover:bg-emerald-800"
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingIngredientId(null)}
                                className="px-2.5 py-1 border border-gray-300 text-gray-600 rounded-lg text-xs font-semibold hover:bg-gray-100"
                              >
                                Cancel
                              </button>
                            </div>
                          )}
                        </div>

                        {!isEditing && (
                          <div className="flex items-center space-x-2 self-end sm:self-center">
                            <button
                              type="button"
                              onClick={() => {
                                setEditingIngredientId(r.ingredient_id);
                                setEditingQuantity(r.quantity_required);
                                setRecipeValidationError(null);
                              }}
                              className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold rounded-lg transition-colors"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                setConfirmDeleteIngredient({
                                  id: r.ingredient_id,
                                  name: r.ingredient_name,
                                })
                              }
                              className="px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-700 text-xs font-bold rounded-lg transition-colors"
                            >
                              Remove ingredient from recipe
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Add New Recipe Ingredient Form */}
            <form onSubmit={handleLinkIngredient} className="p-4 bg-gray-50 rounded-2xl border border-gray-200/80 space-y-3">
              <h4 className="text-xs font-bold uppercase text-gray-800 flex items-center gap-1.5">
                <Plus className="w-3.5 h-3.5 text-[#166534]" />
                Add Ingredient to Recipe
              </h4>

              {ingredients.length === 0 ? (
                <p className="text-xs text-amber-700 bg-amber-50 p-3 rounded-xl border border-amber-200">
                  No ingredients configured in kitchen inventory yet. Please add ingredients to your kitchen first via the <strong>Ingredients</strong> tab.
                </p>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-bold text-gray-600 mb-1">
                        Select Ingredient
                      </label>
                      <select
                        required
                        value={selectedIngredientId}
                        onChange={(e) => {
                          setSelectedIngredientId(e.target.value);
                          setRecipeValidationError(null);
                        }}
                        className="w-full px-3 py-2 bg-white border border-gray-300 rounded-xl text-xs focus:ring-[#166534]"
                      >
                        <option value="">-- Choose from Kitchen Inventory --</option>
                        {ingredients.map((ing) => (
                          <option key={ing.id} value={ing.id}>
                            {ing.name} ({ing.unit})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-bold text-gray-600 mb-1">
                        Quantity Required per Order {selectedIngredientId && `(${ingredients.find((i) => i.id === selectedIngredientId)?.unit || ''})`}
                      </label>
                      <div className="flex items-center space-x-1.5">
                        <input
                          type="number"
                          step="any"
                          min="0.001"
                          required
                          value={recipeQuantity}
                          onChange={(e) => {
                            setRecipeQuantity(parseFloat(e.target.value) || 0);
                            setRecipeValidationError(null);
                          }}
                          className="w-full px-3 py-2 bg-white border border-gray-300 rounded-xl text-xs focus:ring-[#166534]"
                        />
                        {selectedIngredientId && (
                          <span className="text-xs font-bold text-gray-500 bg-gray-200 px-2 py-2 rounded-xl">
                            {ingredients.find((i) => i.id === selectedIngredientId)?.unit || ''}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="w-full py-2.5 bg-[#166534] text-white rounded-xl text-xs font-bold hover:bg-emerald-800 transition-colors shadow-xs"
                  >
                    Save Ingredient to Recipe
                  </button>
                </>
              )}
            </form>

            <div className="flex justify-end pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => {
                  setRecipeModalItem(null);
                  setRecipeValidationError(null);
                  setEditingIngredientId(null);
                }}
                className="px-5 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-xs font-bold transition-colors"
              >
                Close Recipe
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Unlink Confirmation Modal */}
      {confirmDeleteIngredient && recipeModalItem && (
        <div className="fixed inset-0 z-60 bg-black/60 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-red-600 pb-2 border-b border-gray-100">
              <AlertCircle className="w-6 h-6 flex-shrink-0" />
              <h3 className="font-bold text-base text-gray-900">Remove Ingredient From Recipe</h3>
            </div>
            <p className="text-xs text-gray-600 leading-relaxed">
              Are you sure you want to remove <strong className="text-gray-900">{confirmDeleteIngredient.name}</strong> from the <strong className="text-gray-900">{recipeModalItem.name}</strong> recipe?
            </p>
            <div className="p-3 bg-gray-50 rounded-xl text-[11px] text-gray-500 border border-gray-200">
              <strong className="text-gray-700">Safety Notice:</strong> This action deletes <em>only</em> the recipe link. The master ingredient record, kitchen inventory stock, and historical transactions will NOT be deleted.
            </div>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteIngredient(null)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmRemoveIngredient}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition-colors"
              >
                Confirm Removal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Image Upload Modal */}
      {uploadModalItem && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100">
              <div>
                <h3 className="text-base font-bold text-gray-900">Upload Dish Image</h3>
                <p className="text-xs text-gray-500 mt-0.5">{uploadModalItem.name}</p>
              </div>
              <button
                onClick={closeUploadModal}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Error Alert */}
            {modalError && (
              <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-xl text-xs flex items-start gap-2 border border-red-200">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-600" />
                <p className="font-semibold leading-tight">{modalError}</p>
              </div>
            )}

            <div className="space-y-4 py-4">
              {/* Option A: Choose File */}
              <div>
                <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                  Option A: Choose Image File
                </label>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  disabled={uploadingImage}
                  onChange={handleFileChange}
                  className="w-full text-xs text-gray-600 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[#166534] file:text-white hover:file:bg-[#14532d] cursor-pointer"
                />
                <p className="text-[11px] text-gray-400 mt-1">PNG, JPG, JPEG, or WEBP up to 5MB</p>

                {filePreview && (
                  <div className="mt-3 p-3 bg-gray-50 rounded-xl border border-gray-200">
                    <p className="text-[11px] font-bold text-gray-500 mb-2 uppercase">Image Preview</p>
                    <div className="relative w-full h-36 rounded-lg overflow-hidden bg-gray-200">
                      <img
                        src={filePreview}
                        alt="Preview"
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="mt-2.5 flex justify-end">
                      <button
                        type="button"
                        disabled={uploadingImage}
                        onClick={handleUploadSelectedFile}
                        className="px-4 py-2 bg-[#166534] hover:bg-[#14532d] text-white rounded-xl text-xs font-bold transition-colors disabled:opacity-50 flex items-center gap-1.5"
                      >
                        {uploadingImage && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                        <span>{uploadingImage ? 'Uploading...' : 'Upload Image'}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3">
                <div className="h-px bg-gray-200 flex-1" />
                <span className="text-[11px] text-gray-400 font-semibold uppercase">Or</span>
                <div className="h-px bg-gray-200 flex-1" />
              </div>

              {/* Option B: Image Web URL */}
              <div>
                <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                  Option B: Image Web URL
                </label>
                <input
                  type="url"
                  value={uploadImageUrl}
                  disabled={uploadingImage}
                  onChange={(e) => {
                    setUploadImageUrl(e.target.value);
                    setUrlPreviewValid(null);
                    setModalError(null);
                  }}
                  placeholder="https://example.com/dish.jpg"
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
                />

                {uploadImageUrl.trim() && (
                  <div className="mt-3 p-3 bg-gray-50 rounded-xl border border-gray-200">
                    <p className="text-[11px] font-bold text-gray-500 mb-2 uppercase">URL Preview</p>
                    <div className="relative w-full h-36 rounded-lg overflow-hidden bg-gray-200 flex items-center justify-center">
                      <img
                        src={uploadImageUrl.trim()}
                        alt="URL Preview"
                        className="w-full h-full object-cover"
                        onLoad={() => setUrlPreviewValid(true)}
                        onError={() => setUrlPreviewValid(false)}
                      />
                      {urlPreviewValid === false && (
                        <div className="absolute inset-0 bg-red-50/90 flex flex-col items-center justify-center p-2 text-center text-red-600">
                          <AlertCircle className="w-5 h-5 mb-1" />
                          <span className="text-xs font-semibold">Preview unavailable in browser</span>
                          <span className="text-[10px] text-red-500 mt-0.5">Server will validate & download directly</span>
                        </div>
                      )}
                    </div>
                    <div className="mt-2.5 flex justify-end">
                      <button
                        type="button"
                        disabled={uploadingImage || !uploadImageUrl.trim()}
                        onClick={handleSaveImageUrl}
                        className="px-4 py-2 bg-[#166534] hover:bg-[#14532d] text-white rounded-xl text-xs font-bold transition-colors disabled:opacity-50 flex items-center gap-1.5"
                      >
                        {uploadingImage && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                        <span>{uploadingImage ? 'Saving...' : 'Save Image URL'}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end pt-4 border-t border-gray-100">
              <button
                type="button"
                onClick={closeUploadModal}
                className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-xs font-semibold hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
