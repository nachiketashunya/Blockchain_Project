import matplotlib.pyplot as plt

# Provided data
total_students = [3, 9, 18, 36, 54, 72]
total_universities = [20, 20, 20, 20, 20, 20]
total_gas = [305067, 915297, 1830306, 3661188, 5490270, 7321344]

# Group data by number of students
data_by_students = {}
for students, universities, gas in zip(total_students, total_universities, total_gas):
    if students not in data_by_students:
        data_by_students[students] = {'ratio': [], 'gas': []}
    data_by_students[students]['ratio'].append(students / universities)
    data_by_students[students]['gas'].append(gas)

# Plotting lines for each number of students
for students, data in data_by_students.items():
    plt.plot(data['ratio'], data['gas'], marker='o', label=f'{students} Students')

# Adding labels and title
plt.xlabel('Total Students / Total Universities Ratio')
plt.ylabel('Total Gas')
plt.title('Total Gas vs Students/Universities Ratio')

# Adding legends
plt.legend()

# Show the plot
plt.grid(True)
plt.show()
