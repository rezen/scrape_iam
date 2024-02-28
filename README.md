# scrape_iam

## Resources
- https://aws.permissions.cloud/
- https://asecure.cloud/

## Todo
- Parse terraform plan
- Compose policies with resource types
- Exclude actions from policies


```javascript
// Generate categories from AWS
Array.from(document.querySelectorAll('.category-0-1-3')).map(el => {
    const category = el.querySelector('[class*="categoryHeader"]').innerText.toLowerCase().replace(/&/g, '').replace(/[\,\s]+/g, '_')
    const services = Array.from(el.querySelectorAll('a')).map(el => {
       return el.href.split(".amazon.com").pop().split("/")[1];
    }).filter(p => !!p).sort()
    return {category, services};
})
```