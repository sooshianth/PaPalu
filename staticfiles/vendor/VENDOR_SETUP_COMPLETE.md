# Vendor Libraries Setup - In Progress

## Status: Downloads Complete ✓

### Downloaded Libraries:

1. ✅ **jQuery 3.6.0** - `jquery-3.6.0/jquery.min.js`
2. ✅ **jQuery 3.7.1** - `jquery-3.7.1/jquery.min.js`
3. ✅ **Persian Datepicker 1.2.0** - CSS & JS
4. ✅ **Persian Date 1.1.0** - JS
5. ✅ **Vazir Font 30.1.0** - Regular & Bold TTF
6. ✅ **Vazirmatn 33.003** - Font package & CSS
7. ✅ **Bootstrap 5.2.3** - RTL CSS & JS bundle
8. ✅ **Font Awesome 6.2.1** - CSS & webfonts
9. ✅ **Chart.js 3.7.1** - JS
10. ✅ **DataTables 1.13.8** - CSS & JS
11. ✅ **Decimal.js 10.4.3** - JS

## Replacement Progress:

### ✅ Completed:
- `authentication/templates/unified_login.html` - Vazirmatn font
- `perm_manager/templates/perm_manager/base.html` - Vazirmatn font
- `data_exflow/templates/data_exflow/standalone_layout.html` - Bootstrap, FontAwesome, Vazirmatn
- `data_exflow/templates/data_exflow/standalone_layout.html` (scripts) - Bootstrap JS, Chart.js
- `data_exflow/templates/data_exflow/index.html` - Chart.js
- `supply/templates/car_entrance_register.html` - jQuery, Persian Datepicker

### 🔄 Remaining Templates (~20 files):
- supply/templates (raw_material, supplier, transport, etc.) - jQuery, Persian Datepicker, DataTables
- sales/templates (proforma, invoice, product, etc.) - jQuery, Vazir Font (PDF)
- production/templates - jQuery, Decimal.js
- distribution/templates - jQuery, Persian Datepicker, Vazir Font (PDF)

## Next Steps:
1. Complete template replacements
2. Run `python manage.py collectstatic`
3. Test pages for missing resources
4. Create file copies for any 404 errors
