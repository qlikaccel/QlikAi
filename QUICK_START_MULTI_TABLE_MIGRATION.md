# Multiple Table Migration - Quick Start Guide

## 🎯 What You Can Do Now

### Original Single-Table Flow (Still Works!)
```
Summary Page → Click Table → View Details → Export → Publish → Power BI ✅
```

### NEW Multi-Table Migration
```
Summary Page → "Select Multiple" → ☑️☑️☑️ Select Tables → Migrate All → Power BI ✅
```

---

## 📖 Step-by-Step Guide

### Single Table Migration (Unchanged)
1. Navigate to **Summary page**
2. Click any table you want to migrate
3. View the **table summary with LLM analysis**
4. Click **"Continue to Export"** button
5. Choose export format (CSV + DAX)
6. Click **"Publish to Power BI"**
7. Single table created in Power BI ✅

### Multiple Table Migration (NEW!)
1. Navigate to **Summary page**
2. Click **"Select Multiple"** button (top-left, in table list)
   - The button becomes blue/active
   - Checkboxes appear next to all tables
3. **Select tables** by checking the checkboxes:
   - ☑️ Click individual checkboxes
   - OR use **"✔️ All"** to select all tables
   - OR use **"🗑️ Clear"** to deselect all
4. Button changes to **"📤 Migrate X Tables"** (where X = count)
5. Click the **"📤 Migrate X Tables"** button
6. You'll be taken to **Multi-Migration Page** where you can:
   - See all selected tables
   - Choose export format
   - Review table counts & record numbers
7. Click **"📤 Migrate to Power BI"**
8. Wait for processing (⏳ 1-5 minutes depending on data size)
9. Multiple tables created in Power BI ✅

---

## 🎛️ Export Format Options

### Combined Export (CSV + DAX)
- Creates Power BI datasets with both data and measures
- Better for creating visualizations
- Includes example measures
- **Recommended** ⭐

### Separate Datasets
- Creates individual datasets for each table
- Useful if you want isolated data model
- Can combine later with Power BI relationships

---

## 💡 Pro Tips

- **Quick Selection**: Use "✔️ All" button to select all tables at once
- **Quick Clear**: Use "🗑️ Clear" to deselect without exiting multi-select mode
- **Fast Switching**: Exit multi-select mode by clicking the button again (reset for single-table view)
- **Test First**: Start with 2-3 tables to verify format before migrating all
- **Naming**: Each table keeps its original name in Power BI
- **Data**: No data is lost - everything is permanent in Power BI Cloud

---

## ⚠️ Important Notes

1. **Large Datasets**: If tables have 100K+ rows, migration may take 2-5 minutes
2. **Network**: Ensure stable internet during migration (don't close browser)
3. **Browser**: Works on Chrome, Edge, Firefox (not tested on IE)
4. **Mobile**: Limited UI on small screens - use desktop/tablet for better experience
5. **Errors**: If migration fails, check backend is running (`python run_backend.ps1`)

---

## 🔧 Troubleshooting

### "Select Multiple" button not appearing
- **Solution**: Refresh page, ensure you're on Summary page

### Checkboxes appear but won't select
- **Solution**: Check browser console for errors (F12)
- Make sure tables have loaded successfully

### Segment fails during migration
- **Solution**: Check that backend is running
- Verify table data is not corrupted
- Try with smaller dataset first

### Button shows "📤 Migrate 0 Tables"
- **Solution**: You haven't selected any tables yet
- Click checkboxes to select at least one table

---

## 🚀 Next Features Coming Soon

- [ ] Progress bar showing X of Y tables migrated
- [ ] Ability to rename tables before migration
- [ ] Merge multiple tables into single dataset
- [ ] Scheduled/recurring migrations
- [ ] Migration history
- [ ] Power query template support

---

## 📞 Support

If you encounter any issues:
1. Check the error message on screen
2. Look at browser console (F12 → Console tab)
3. Verify backend API is running
4. Check network tab for failed requests
5. Try with a single smaller table first

---

**Happy migrating!** 🎉
